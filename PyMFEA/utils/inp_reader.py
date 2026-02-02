import re
import numpy as np

class InpParser:
    """
    简化封装的 Abaqus INP 文本解析器。

    当前实现覆盖了本项目求解所需的主流关键字：
        *SYSTEM, *NODE, *ELEMENT, *NSET, *ELSET,
        *SURFACE, *BOUNDARY, *CLOAD, *DSLOAD,
        *MATERIAL, *ELASTIC, *DENSITY

    解析结果以纯 Python 容器返回，便于和后处理、GUI 交互。
    """
    
    def __init__(self):
        self.nodes = {}      # {node_id: [x, y, z]}
        self.elements = {}   # {elem_id: [n1, n2, ...]}
        self.nsets = {}      # {set_name: [id1, id2, ...]}
        self.elsets = {}     # {set_name: [id1, id2, ...]}
        self.surfaces = {}   # {surf_name: [(eid, face_id), ...]}
        self.materials = {}  # {mat_name: {'E': float, 'nu': float, 'density': float}}
        self.constraints = [] # list of dict
        self.loads = []       # list of dict
        
        # 坐标变换状态（*SYSTEM）
        self.origin = np.array([0.0, 0.0, 0.0])
        self.rotation = np.eye(3)
        
        # 材料解析状态：记录最近一次 *MATERIAL 声明的材料名
        self.current_material = None

    def read(self, filename):
        """从 INP 文件中读取并解析全部支持的关键字。"""
        print(f"正在解析 INP 文件: {filename} ...")
        
        with open(filename, 'r') as f:
            # 预读取所有行，去除换行符
            all_lines = [line.strip() for line in f.readlines()]
            
        idx = 0
        total_lines = len(all_lines)
        
        while idx < total_lines:
            line = all_lines[idx]
            
            # 跳过空行和注释
            if not line or line.startswith('**'):
                idx += 1
                continue
            
            if line.startswith('*'):
                keyword_line = line.upper()
                
                # --- *SYSTEM: 全局坐标变换 ---
                if '*SYSTEM' in keyword_line:
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    vals = self._parse_csv_matrix(blk)
                    if len(vals) > 0:
                        # P1: 原点坐标
                        p1 = np.array(vals[0][:3])
                        # P2 等信息暂未用到，如后续需要可扩展为完整旋转矩阵
                        self.origin = p1
                    idx = next_idx
                    continue

                # --- *NODE: 节点坐标 ---
                elif '*NODE' in keyword_line and 'OUTPUT' not in keyword_line:
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    raw_data = self._parse_csv_matrix(blk)
                    
                    for row in raw_data:
                        if len(row) < 4: continue
                        nid = int(row[0])
                        local_coords = np.array(row[1:4])
                        # 应用上一步 *SYSTEM 定义的平移/旋转
                        global_coords = self.origin + local_coords @ self.rotation
                        self.nodes[nid] = global_coords.tolist()
                    
                    idx = next_idx
                    continue
                
                # --- *ELEMENT: 单元拓扑 ---
                elif '*ELEMENT' in keyword_line and 'OUTPUT' not in keyword_line:
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    raw_data = self._parse_csv_matrix(blk)
                    
                    for row in raw_data:
                        eid = int(row[0])
                        # 节点 ID 转整数，忽略 0 作为补零占位
                        nids = [int(x) for x in row[1:] if x != 0]
                        self.elements[eid] = nids
                        
                    idx = next_idx
                    continue
                
                # --- *NSET: 节点集合 ---
                elif '*NSET' in keyword_line:
                    name = self._extract_param(keyword_line, 'NSET')
                    is_gen = 'GENERATE' in keyword_line
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    
                    if name:
                        ids = self._parse_ids(blk, is_gen)
                        if name not in self.nsets: self.nsets[name] = []
                        self.nsets[name].extend(ids)
                    
                    idx = next_idx
                    continue
                
                # --- *ELSET: 单元集合 ---
                elif '*ELSET' in keyword_line:
                    name = self._extract_param(keyword_line, 'ELSET')
                    is_gen = 'GENERATE' in keyword_line
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    
                    if name:
                        name_upper = name.upper()  # 统一转大写存储，避免大小写问题
                        ids = self._parse_ids(blk, is_gen)
                        if name_upper not in self.elsets: self.elsets[name_upper] = []
                        self.elsets[name_upper].extend(ids)
                        
                    idx = next_idx
                    continue

                # --- *SURFACE: 面集合（后续用于压力等面载荷） ---
                elif '*SURFACE' in keyword_line:
                    name = self._extract_param(keyword_line, 'NAME')
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    
                    if name:
                        name_upper = name.upper()  # 统一转大写存储
                        if name_upper not in self.surfaces: self.surfaces[name_upper] = []
                        for l in blk:
                            parts = self._split_line(l)
                            if len(parts) >= 2:
                                # 形式：Eset/Eid, FaceID (S1, S2, ...)
                                self.surfaces[name_upper].append((parts[0].upper(), parts[1].upper()))
                                
                    idx = next_idx
                    continue

                # --- *BOUNDARY: 约束条件 ---
                elif '*BOUNDARY' in keyword_line:
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    self._process_boundary_block(blk)
                    idx = next_idx
                    continue

                # --- *CLOAD: 节点集中力 ---
                elif '*CLOAD' in keyword_line:
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    self._process_cload_block(blk)
                    idx = next_idx
                    continue

                # --- *DSLOAD: 面载荷（压力） ---
                elif '*DSLOAD' in keyword_line:
                    blk, next_idx = self._read_data_block(all_lines, idx + 1)
                    self._process_dsload_block(blk)
                    idx = next_idx
                    continue

                # --- *MATERIAL: 材料名称 ---
                elif '*MATERIAL' in keyword_line:
                    name = self._extract_param(keyword_line, 'NAME')
                    if name:
                        self.current_material = name.upper()
                        if self.current_material not in self.materials:
                            self.materials[self.current_material] = {
                                'E': None,
                                'nu': None,
                                'density': None
                            }
                    idx += 1
                    continue

                # --- *ELASTIC: 弹性参数 ---
                elif '*ELASTIC' in keyword_line:
                    if self.current_material:
                        blk, next_idx = self._read_data_block(all_lines, idx + 1)
                        self._process_elastic_block(blk)
                        idx = next_idx
                    else:
                        idx += 1
                    continue

                # --- *DENSITY: 密度 ---
                elif '*DENSITY' in keyword_line:
                    if self.current_material:
                        blk, next_idx = self._read_data_block(all_lines, idx + 1)
                        self._process_density_block(blk)
                        idx = next_idx
                    else:
                        idx += 1
                    continue

                # --- *PLASTIC: 塑性参数 ---
                elif '*PLASTIC' in keyword_line:
                    if self.current_material:
                        blk, next_idx = self._read_data_block(all_lines, idx + 1)
                        self._process_plastic_block(blk)
                        idx = next_idx
                    else:
                        idx += 1
                    continue

            # 如果不是关键字也不是空行，继续下一行
            idx += 1
            
        return {
            'nodes': self.nodes,
            'elements': self.elements,
            'nsets': self.nsets,
            'elsets': self.elsets,
            'surfaces': self.surfaces,
            'materials': self.materials,
            'constraints': self.constraints,
            'loads': self.loads
        }

    # ================= 辅助方法 (Helpers) =================

    def _read_data_block(self, lines, idx):
        """读取从给定行开始、直到下一条关键字行（以 * 开头）的数据块。"""
        blk = []
        while idx < len(lines):
            l = lines[idx].strip()
            # 如果遇到新关键字 (且不是注释 **)，则停止
            if l.startswith('*') and not l.startswith('**'):
                break
            if l and not l.startswith('**'):
                blk.append(l)
            idx += 1
        return blk, idx

    def _parse_csv_matrix(self, blk):
        """解析逗号分隔的数值矩阵，自动忽略非数值项。"""
        res = []
        for line in blk:
            # 移除结尾逗号，处理换行续写的情况
            clean_line = line.rstrip(',') 
            parts = clean_line.split(',')
            row = []
            for p in parts:
                try:
                    row.append(float(p))
                except ValueError:
                    pass
            if row:
                res.append(row)
        return res

    def _parse_ids(self, blk, is_gen):
        """解析 ID 列表，支持 Abaqus 中的 GENERATE 语法。"""
        vals = self._parse_csv_matrix(blk)
        ids = []
        if is_gen:
            for row in vals:
                if len(row) >= 3:
                    start, end, step = int(row[0]), int(row[1]), int(row[2])
                    ids.extend(range(start, end + 1, step))
        else:
            for row in vals:
                ids.extend([int(x) for x in row])
        return ids

    def _extract_param(self, header, key):
        """从关键字行中提取形如 KEY=VALUE 的参数值（例如 NSET=XYZ）。"""
        parts = header.split(',')
        for p in parts:
            if '=' in p:
                k, v = p.split('=')
                if k.strip() == key:
                    return v.strip()
        return None

    def _split_line(self, line):
        """按逗号拆分一行字符串，并去除两端空白。"""
        return [x.strip() for x in line.split(',') if x.strip()]

    def _resolve_ids(self, target, set_map):
        """
        根据字符串解析为 ID 列表。

        若 target 在 set_map 中，则返回对应集合；
        否则尝试将其解析为单个整数 ID。
        """
        target = target.upper()
        if target in set_map:
            return set_map[target]
        else:
            try:
                return [int(target)]
            except ValueError:
                return []

    # ================= 业务逻辑处理 =================

    def _process_boundary_block(self, blk):
        """解析 *BOUNDARY 数据块并填充 self.constraints 列表。"""
        for line in blk:
            parts = self._split_line(line)
            if not parts: continue
            
            target = parts[0]
            target_upper = target.upper()
            
            # 检查 target 是否是 NSET 名称
            is_set = target_upper in self.nsets
            
            dofs = []
            val = 0.0
            
            # 逻辑分支：
            #   Type 1: Node/Set, start_dof, end_dof, value
            #   Type 2: Node/Set, 关键字简写 (ENCASTRE, PINNED, XSYMM 等)
            if len(parts) >= 2:
                p2 = parts[1].upper()
                # 尝试转数字
                try:
                    st = int(p2)
                    # 数字：起始自由度
                    if len(parts) >= 3:
                        ed = int(parts[2])
                    else:
                        ed = st
                    
                    if len(parts) >= 4:
                        val = float(parts[3])
                    
                    dofs = list(range(st, ed + 1))
                except ValueError:
                    # 非数字：使用 Abaqus 的字符串简写 (ENCASTRE 等)
                    if p2 == 'XSYMM': dofs = [1, 5, 6]
                    elif p2 == 'YSYMM': dofs = [2, 4, 6]
                    elif p2 == 'ZSYMM': dofs = [3, 4, 5]
                    elif p2 == 'PINNED': dofs = [1, 2, 3]
                    elif p2 == 'ENCASTRE': dofs = [1, 2, 3, 4, 5, 6]
            
            # 如果 target 是集合名，则以 set_name 形式保存，后续在装配阶段展开
            if is_set:
                for d in dofs:
                    # 注意：Abaqus 1-based -> Python 0-based
                    if 1 <= d <= 6:  # 支持所有自由度
                        self.constraints.append({
                            'set_name': target_upper,  # 保存set名称
                            'dof': d - 1,
                            'value': val
                        })
            else:
                # 否则尝试解析为单个节点 ID
                ids = self._resolve_ids(target, self.nsets)
                for nid in ids:
                    for d in dofs:
                        # 注意：Abaqus 1-based -> Python 0-based
                        if 1 <= d <= 6:  # 支持所有自由度
                            self.constraints.append({
                                'node_id': nid,
                                'dof': d - 1,
                                'value': val
                            })

    def _process_cload_block(self, blk):
        """解析 *CLOAD 数据块并填充 self.loads 列表。"""
        for line in blk:
            parts = self._split_line(line)
            if len(parts) < 3: continue
            
            target = parts[0]
            target_upper = target.upper()
            dof = int(parts[1])
            mag = float(parts[2])
            
            # 检查 target 是否是 NSET 名称
            is_set = target_upper in self.nsets
            
            if is_set:
                # 若为集合则仅记录 set_name，求解阶段再展开为节点力
                self.loads.append({
                    'set_name': target_upper,
                    'dof': dof - 1,
                    'value': mag
                })
            else:
                # 否则尝试解析为节点 ID
                ids = self._resolve_ids(target, self.nsets)
                for nid in ids:
                    self.loads.append({
                        'node_id': nid,
                        'dof': dof - 1,
                        'value': mag
                    })

    def _process_dsload_block(self, blk):
        """
        处理面载荷 (*DSLOAD)。

        既保存 surface 级别的载荷信息用于可视化，
        也将其近似展开为等效节点力并添加到 self.loads 供求解器使用。
        """
        for line in blk:
            parts = self._split_line(line)
            if len(parts) < 3: continue
            
            surf_name = parts[0].upper()
            # parts[1] 通常为 'P' (Pressure)，此处假定为均匀压力
            try:
                press_mag = float(parts[2])
            except ValueError:
                continue

            surf_name_upper = surf_name.upper()
            if surf_name_upper in self.surfaces:
                face_defs = self.surfaces[surf_name_upper]

                # 先保存 Surface 载荷信息（用于显示）
                self.loads.append({
                    'surface_name': surf_name_upper,
                    'type': 'Pressure',
                    'value': press_mag
                })
                
                # 然后展开成节点力（用于求解器，并在记录中标记来源）
                for target_str, face_id in face_defs:
                    # target_str 可能是 ELSET 名称，也可能是单个 Element ID
                    eids = self._resolve_ids(target_str.upper(), self.elsets)
                    
                    for eid in eids:
                        if eid not in self.elements: continue
                        elem_nodes = self.elements[eid]  # list of node IDs
                        
                        # 获取面上的节点 ID 列表
                        fnodes = self._get_face_nodes(elem_nodes, face_id.upper())
                        if len(fnodes) < 3: continue
                        
                        # 获取该面的节点坐标
                        coords = []
                        valid_face = True
                        for nid in fnodes:
                            if nid in self.nodes:
                                coords.append(self.nodes[nid])
                            else:
                                valid_face = False
                                break
                        if not valid_face: continue
                        
                        # 计算几何属性（面积与法向）
                        area, normal = self._calc_face_geometry(coords)
                        
                        # 计算总力向量：F = -p * A * n
                        total_force = -press_mag * area * normal
                        
                        # 简化做法：将总力均匀分配到该面的所有节点
                        node_force = total_force / len(fnodes)
                        
                        for nid in fnodes:
                            for d in range(3):
                                if abs(node_force[d]) > 1e-9:
                                    self.loads.append({
                                        'node_id': nid,
                                        'dof': d, # 0,1,2
                                        'value': node_force[d],
                                        'from_surface': surf_name_upper  # 标记来源
                                    })

    def _get_face_nodes(self, node_ids, face_id):
        """
        获取 C3D8 单元上指定面的节点 ID。

        约定的节点顺序：
            1-2-3-4 为底面，5-6-7-8 为顶面。
        """
        # 说明：
        #   为保证法向量朝外，一些实现会调整面节点的排列顺序（如 S1=[1,4,3,2]）。
        #   这里主要关心节点集合本身，因此只需保持与几何计算一致的顺序即可。

        # 为了便于索引，node_ids 使用 0-based 索引
        n = node_ids
        if len(n) < 8: return []
        
        idx = []
        if face_id == 'S1': idx = [0, 3, 2, 1]     # Bottom
        elif face_id == 'S2': idx = [4, 5, 6, 7]   # Top
        elif face_id == 'S3': idx = [0, 1, 5, 4]   # Front
        elif face_id == 'S4': idx = [1, 2, 6, 5]   # Right
        elif face_id == 'S5': idx = [2, 3, 7, 6]   # Back
        elif face_id == 'S6': idx = [3, 0, 4, 7]   # Left
        
        return [n[i] for i in idx]

    def _calc_face_geometry(self, coords):
        """
        根据四个顶点坐标近似计算平面四边形的面积和法向量。

        Args:
            coords (list[list[float]]): 顶点坐标列表 [x, y, z]

        Returns:
            tuple[float, np.ndarray]: (面积, 单位法向量)。
        """
        # coords: list of [x, y, z]
        pts = np.array(coords)
        if len(pts) < 3: return 0.0, np.zeros(3)
        
        # 对四边形面，采用对角线叉积的一半近似计算面积：
        #   A = P3 - P1, B = P4 - P2,  normal ~ A × B
        
        if len(pts) == 4:
            v1 = pts[2] - pts[0] # Diagonal 1
            v2 = pts[3] - pts[1] # Diagonal 2
            cp = np.cross(v1, v2)
            vn = np.linalg.norm(cp)
            area = 0.5 * vn
            normal = cp / (vn + 1e-20)
            return area, normal
        else:
            return 0.0, np.zeros(3)

    def _process_elastic_block(self, blk):
        """处理 *ELASTIC 数据块，提取 E 和 nu"""
        if not self.current_material:
            return
        
        # 解析数值数据
        vals = self._parse_csv_matrix(blk)
        if len(vals) > 0 and len(vals[0]) >= 2:
            # 第一行：E, nu
            E = float(vals[0][0])
            nu = float(vals[0][1])
            self.materials[self.current_material]['E'] = E
            self.materials[self.current_material]['nu'] = nu

    def _process_density_block(self, blk):
        """处理 *DENSITY 数据块，提取密度值"""
        if not self.current_material:
            return
        
        # 解析数值数据
        vals = self._parse_csv_matrix(blk)
        if len(vals) > 0 and len(vals[0]) >= 1:
            # 第一行第一个值：密度
            density = float(vals[0][0])
            self.materials[self.current_material]['density'] = density

    def _process_plastic_block(self, blk):
        """
        处理 *PLASTIC 数据块，提取塑性参数
        
        Abaqus 格式: yield_stress, plastic_strain
        第一行通常是初始屈服应力 (plastic_strain = 0)
        """
        if not self.current_material:
            return
        
        vals = self._parse_csv_matrix(blk)
        if len(vals) > 0 and len(vals[0]) >= 1:
            # 第一行第一个值：屈服应力
            yield_stress = float(vals[0][0])
            # 第二个值(如果有)：塑性应变，用于硬化曲线，简化处理暂不使用
            plastic_strain = float(vals[0][1]) if len(vals[0]) >= 2 else 0.0
            
            self.materials[self.current_material]['plastic'] = {
                'yield_stress': yield_stress,
                'hardening': 0.0  # 理想塑性，无硬化
            }
