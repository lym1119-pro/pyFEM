import numpy as np
import pyvista as pv

class FEMVisualizer:
    """
    有限元结果可视化辅助类。

    主要负责：
    - 将节点／单元数据转换为 PyVista 非结构化网格
    - 绑定位移、应力等标量／矢量场
    - 提供常用的颜色映射与取值范围工具
    """
    
    # 常用的颜色映射选项
    AVAILABLE_CMAPS = [
        'jet', 'viridis', 'plasma', 'inferno', 'magma', 'coolwarm',
        'rainbow', 'turbo', 'hot', 'cool', 'spring', 'summer', 'autumn', 'winter',
        'bone', 'copper', 'pink', 'gray', 'RdYlBu', 'RdYlGn', 'RdBu', 'Spectral'
    ]
    
    def parse_mesh_to_vtk(self, nodes, elements, displacement=None, stress=None, stress_components=None):
        """
        将节点和单元转换为 PyVista 非结构化网格

        支持的节点输入格式：
            - dict: {node_id: [x, y, z]}  或  {node_id: Node 对象}
            - list: [Node 对象]

        Args:
            nodes: 节点集合，字典或列表形式
            elements: 单元集合，字典或 Element 对象列表
            displacement (np.ndarray | None): 节点位移 (N×3)
            stress (np.ndarray | None): 节点标量应力（例如 Von Mises）
            stress_components (np.ndarray | None): 节点应力分量 (N×6)

        Returns:
            pv.UnstructuredGrid: 已附加结果字段的网格对象。
        """
        # 1. 处理节点数据
        if isinstance(nodes, dict):
            # 检查第一个值是什么类型
            first_value = next(iter(nodes.values()))
            if isinstance(first_value, list) and len(first_value) == 3:
                # INP格式: {node_id: [x, y, z]}
                sorted_ids = sorted(nodes.keys())
                node_coords = np.array([nodes[nid] for nid in sorted_ids])
                id_map = {nid: i for i, nid in enumerate(sorted_ids)}
            else:
                # 对象格式: {node_id: Node对象}
                sorted_ids = sorted(nodes.keys())
                node_coords = np.array([nodes[nid].coords for nid in sorted_ids])
                id_map = {nid: i for i, nid in enumerate(sorted_ids)}
        else:
            # 列表格式: [Node对象]
            node_coords = np.array([n.coords for n in nodes])
            id_map = {n.id: i for i, n in enumerate(nodes)}

        # 2. 处理单元连接关系（目前仅支持 8 节点六面体）
        cells = []
        cell_types = []
        
        if isinstance(elements, dict):
            # INP格式: {elem_id: [n1, n2, ...]}
            for elem_nodes in elements.values():
                cells.append(8)  # 8节点六面体
                cells.extend([id_map[nid] for nid in elem_nodes])
                cell_types.append(12)  # VTK_HEXAHEDRON
        else:
            # 对象格式: [Element对象]
            for elem in elements:
                cells.append(8)
                cells.extend([id_map[n.id] for n in elem.nodes])
                cell_types.append(12) # VTK_HEXAHEDRON

        # 3. 创建 PyVista 网格
        grid = pv.UnstructuredGrid(cells, cell_types, node_coords)

        # 4. 绑定结果
        if displacement is not None:
            grid.point_data["Displacement"] = displacement
            
        if stress is not None:
            grid.point_data["VonMises"] = stress
            
        if stress_components is not None:
            # 添加应力分量
            grid.point_data["S11"] = stress_components[:, 0]  # σx
            grid.point_data["S22"] = stress_components[:, 1]  # σy
            grid.point_data["S33"] = stress_components[:, 2]  # σz
            grid.point_data["S12"] = stress_components[:, 3]  # τxy
            grid.point_data["S23"] = stress_components[:, 4]  # τyz
            grid.point_data["S13"] = stress_components[:, 5]  # τxz

        return grid

    @staticmethod
    def calc_von_mises(stress_tensor):
        """
        根据六分量工程应力计算 Von Mises 等效应力。

        Args:
            stress_tensor (np.ndarray): 形状为 (N, 6)，顺序为
                [σx, σy, σz, τxy, τyz, τzx]

        Returns:
            np.ndarray: 形状为 (N,) 的 Von Mises 应力。
        """
        sx = stress_tensor[:, 0]
        sy = stress_tensor[:, 1]
        sz = stress_tensor[:, 2]
        sxy = stress_tensor[:, 3]
        syz = stress_tensor[:, 4]
        szx = stress_tensor[:, 5]
        
        term1 = (sx - sy)**2 + (sy - sz)**2 + (sz - sx)**2
        term2 = 6 * (sxy**2 + syz**2 + szx**2)
        
        vm = np.sqrt(0.5 * (term1 + term2))
        return vm
    
    @staticmethod
    def get_scalar_range(grid, scalar_name, custom_range=None):
        """
        获取网格中指定标量字段的取值范围。

        Args:
            grid: PyVista 网格对象
            scalar_name (str): 标量数据名称
            custom_range (Sequence[float] | None): 自定义范围 [min, max]。
                若为 None，则自动从数据中统计。
        Returns:
            tuple[float, float]: (min_value, max_value)。若字段不存在则返回 (None, None)。
        """
        if scalar_name not in grid.point_data:
            return None, None
        
        data = grid.point_data[scalar_name]
        if custom_range is not None and len(custom_range) == 2:
            return custom_range[0], custom_range[1]
        
        return float(np.min(data)), float(np.max(data))
    
    @staticmethod
    def validate_cmap(cmap_name):
        """
        验证颜色映射名称是否有效。

        Args:
            cmap_name (str): 颜色映射名称
        Returns:
            str: 一个可在 PyVista / Matplotlib 中使用的颜色映射名称。
        """
        if cmap_name in FEMVisualizer.AVAILABLE_CMAPS:
            return cmap_name
        # 如果不在预设列表中，尝试使用 Matplotlib 的内置映射
        try:
            import matplotlib.pyplot as plt
            plt.get_cmap(cmap_name)
            return cmap_name
        except Exception:
            return 'jet'  # 默认返回jet
    
    def create_bc_actors(self, model_data, nodes_map=None):
        """
        为边界条件 (Boundary Conditions) 创建几何标记（锥体 glyph）。

        约束的几何解释：
            - 平动自由度 (dof 0,1,2)：在对应坐标轴方向绘制尖锥
            - 转动自由度 (dof 3,4,5)：使用与转轴垂直的方向进行可视化

        Args:
            model_data (dict): 至少包含 'constraints' 与 'nodes' 的模型数据字典。
            nodes_map (dict | None): 节点坐标映射 {node_id: [x, y, z]} 或 Node 对象。
                若为 None，则默认从 model_data['nodes'] 中获取。

        Returns:
            list[dict]: 包含绘制所需 PolyData 以及颜色信息的字典列表。
        """
        actors = []
        
        if 'constraints' not in model_data or not model_data['constraints']:
            return actors
        
        # 获取节点数据
        if nodes_map is None:
            nodes_map = model_data.get('nodes', {})
        
        if not nodes_map:
            return actors
        
        # 处理节点格式
        if isinstance(nodes_map, dict):
            first_value = next(iter(nodes_map.values()))
            if isinstance(first_value, list) and len(first_value) == 3:
                # INP格式: {node_id: [x, y, z]}
                node_coords_map = {nid: np.array(coords) for nid, coords in nodes_map.items()}
            else:
                # 对象格式: {node_id: Node对象}
                node_coords_map = {nid: np.array(node.coords) for nid, node in nodes_map.items()}
        else:
            return actors
        
        # 获取 nsets 用于展开 set_name 约束
        nsets = model_data.get('nsets', {})
        
        # 计算网格边界框对角线长度用于缩放符号尺寸
        all_coords = np.array(list(node_coords_map.values()))
        if len(all_coords) == 0:
            return actors
        
        bbox_min = np.min(all_coords, axis=0)
        bbox_max = np.max(all_coords, axis=0)
        bbox_diagonal = np.linalg.norm(bbox_max - bbox_min)
        # 约束符号高度取对角线的 1%，为短而尖的圆锥，尖端在节点处
        glyph_height = bbox_diagonal * 0.01
        
        # 收集所有约束节点
        bc_points = []
        bc_directions = []
        
        for cons in model_data['constraints']:
            node_ids = []
            
            # 处理 set_name 约束
            if 'set_name' in cons:
                set_name = cons['set_name']
                if set_name in nsets:
                    node_ids = nsets[set_name]
                else:
                    continue
            elif 'node_id' in cons:
                node_ids = [cons['node_id']]
            else:
                continue
            
            dof = cons.get('dof', 0)
            
            # 为每个节点创建约束可视化
            for nid in node_ids:
                if nid not in node_coords_map:
                    continue
                
                point = node_coords_map[nid]
                bc_points.append(point)
                
                # 根据 DOF 确定方向
                # DOF 0=x, 1=y, 2=z, 3=rx, 4=ry, 5=rz
                if dof < 3:
                    # 平动自由度：方向沿坐标轴
                    direction = np.zeros(3)
                    direction[dof] = 1.0
                else:
                    # 转动自由度：使用垂直于坐标轴的方向
                    direction = np.zeros(3)
                    if dof == 3:  # rx -> 绕x轴，显示为y方向
                        direction[1] = 1.0
                    elif dof == 4:  # ry -> 绕y轴，显示为z方向
                        direction[2] = 1.0
                    elif dof == 5:  # rz -> 绕z轴，显示为x方向
                        direction[0] = 1.0
                
                bc_directions.append(direction)
        
        if len(bc_points) == 0:
            return actors
        
        # 创建 PolyData
        bc_points_array = np.array(bc_points)
        bc_directions_array = np.array(bc_directions)
        
        # 调整点位置：圆锥的尖端应落在节点位置
        # 由于 Cone 的尖端在 z=0，需要将点沿方向反向平移高度的一半
        adjusted_bc_points = bc_points_array - bc_directions_array * glyph_height * 0.5
        
        # 创建点云
        point_cloud = pv.PolyData(adjusted_bc_points)
        point_cloud['vectors'] = bc_directions_array
        
        # 使用 Cone 作为 Glyph（direction=(0,0,-1) 使尖端指向局部 -z）
        # 半径约为高度的 0.15 倍，使圆锥既尖锐又清晰
        cone = pv.Cone(radius=glyph_height * 0.15, height=glyph_height, direction=(0, 0, -1))
        
        # 创建 Glyph（不使用缩放数组，因为 Cone 已设置好物理尺寸）
        glyph = point_cloud.glyph(
            orient='vectors',
            scale=False,
            factor=1.0,  # 使用 factor=1.0 应用 Cone 的原始尺寸
            geom=cone
        )
        
        # 返回 PolyData 对象和颜色信息，交由外部 plotter 创建 Actor
        actors.append({
            'mesh': glyph,
            'color': '#FF9900'
        })
        
        return actors
    
    def create_load_actors(self, model_data, nodes_map=None):
        """
        为节点载荷 (Loads) 创建箭头形式的几何标记。

        目前只可视化平动自由度上的力（dof 0,1,2），
        且假定载荷已展开为节点力或通过 NSET 映射到节点 ID。

        Args:
            model_data (dict): 至少包含 'loads' 与 'nodes' 的模型数据字典。
            nodes_map (dict | None): 节点坐标映射 {node_id: [x, y, z]} 或 Node 对象。
                若为 None，则默认从 model_data['nodes'] 中获取。

        Returns:
            list[dict]: 包含用于绘制的 PolyData 和颜色信息的字典列表。
        """
        actors = []
        
        if 'loads' not in model_data or not model_data['loads']:
            return actors
        
        # 获取节点数据
        if nodes_map is None:
            nodes_map = model_data.get('nodes', {})
        
        if not nodes_map:
            return actors
        
        # 处理节点格式
        if isinstance(nodes_map, dict):
            first_value = next(iter(nodes_map.values()))
            if isinstance(first_value, list) and len(first_value) == 3:
                # INP格式: {node_id: [x, y, z]}
                node_coords_map = {nid: np.array(coords) for nid, coords in nodes_map.items()}
            else:
                # 对象格式: {node_id: Node对象}
                node_coords_map = {nid: np.array(node.coords) for nid, node in nodes_map.items()}
        else:
            return actors
        
        # 获取 nsets 用于展开 set_name 载荷
        nsets = model_data.get('nsets', {})
        
        # 计算网格边界框对角线长度用于决定箭头长度
        all_coords = np.array(list(node_coords_map.values()))
        if len(all_coords) == 0:
            return actors
        
        bbox_min = np.min(all_coords, axis=0)
        bbox_max = np.max(all_coords, axis=0)
        bbox_diagonal = np.linalg.norm(bbox_max - bbox_min)
        
        # 收集所有载荷
        load_points = []
        load_vectors = []
        
        for load in model_data['loads']:
            # 跳过 surface 载荷（它们已经展开成节点力了）
            if 'surface_name' in load:
                continue
            
            node_ids = []
            
            # 处理 set_name 载荷
            if 'set_name' in load:
                set_name = load['set_name']
                if set_name in nsets:
                    node_ids = nsets[set_name]
                else:
                    continue
            elif 'node_id' in load:
                node_ids = [load['node_id']]
            else:
                continue
            
            dof = load.get('dof', 0)
            value = load.get('value', 0.0)
            
            # 只处理平动自由度 (0, 1, 2) 的载荷
            if dof >= 3:
                continue
            
            # 为每个节点创建载荷可视化
            for nid in node_ids:
                if nid not in node_coords_map:
                    continue
                
                point = node_coords_map[nid]
                load_points.append(point)
                
                # 根据 DOF 和 value 确定力向量
                force_vector = np.zeros(3)
                force_vector[dof] = value
                
                load_vectors.append(force_vector)
        
        if len(load_points) == 0:
            return actors
        
        # 创建 PolyData
        load_points_array = np.array(load_points)
        load_vectors_array = np.array(load_vectors)
        
        # 计算力向量的大小用于缩放
        force_magnitudes = np.linalg.norm(load_vectors_array, axis=1)
        max_force = np.max(force_magnitudes) if len(force_magnitudes) > 0 else 1.0
        
        # 归一化方向向量
        load_directions = load_vectors_array.copy()
        for i in range(len(load_directions)):
            mag = np.linalg.norm(load_directions[i])
            if mag > 1e-10:
                load_directions[i] = load_directions[i] / mag
            else:
                load_directions[i] = np.array([1, 0, 0])  # 默认方向
        
        # 箭头长度取对角线的 4%，保证在大多数模型尺寸下可见而不过分夸张
        arrow_length = bbox_diagonal * 0.04
        
        # 调整点位置，使箭头尾部落在节点处：
        # 箭头从 (point - direction * arrow_length) 指向 point
        adjusted_load_points = load_points_array - load_directions * arrow_length
        
        # 创建点云（使用调整后的点位置）
        point_cloud = pv.PolyData(adjusted_load_points)
        point_cloud['vectors'] = load_directions
        
        # 使用 Arrow 作为 Glyph。
        # PyVista 的 Arrow 构造函数在不同版本中的参数略有差异，
        # 这里先尝试“详细参数”，失败时退化为无参构造以提高兼容性。
        try:
            # 尝试使用标准参数（PyVista 0.32+）
            arrow = pv.Arrow(
                tip_length=0.25,
                tip_radius=0.1,
                shaft_radius=0.05,
                shaft_resolution=10,
                tip_resolution=10
            )
        except (TypeError, ValueError):
            # 如果参数不匹配，使用最简单的创建方式（无参数）
            arrow = pv.Arrow()
        
        # 创建 Glyph：使用统一缩放因子，避免因力值尺度不同导致箭头过大或不可见
        glyph = point_cloud.glyph(
            orient='vectors',
            scale=False,  # 不使用缩放数组，使用统一的 factor
            factor=arrow_length,  # 使用箭头长度作为缩放因子
            geom=arrow
        )
        
        # 返回 PolyData 对象和颜色信息，由外部 plotter 创建实际 Actor
        actors.append({
            'mesh': glyph,
            'color': '#FFFF00'
        })
        
        return actors