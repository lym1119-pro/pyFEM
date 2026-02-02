import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
import time
import copy

# === 导入核心模块 ===
from utils.inp_reader import InpParser
from core.node import Node
from core.materials import MaterialFactory, J2PlasticMaterial
from utils.visualizer import FEMVisualizer

# 1. 线性相关
from core.element import C3D8Element
from core.quadrature import Quadrature
from solver.assembler import GlobalAssembler
from solver.LinearSolver import LinearSolver

# 2. 非线性相关 (新增)
from core.element_nonlinear import C3D8_TL, C3D8_UL
from solver.nonlinear_solver import NonlinearSolver

class SolverWorker(QThread):
    """
    求解主线程
    职责：
    1. 解析 INP
    2. 根据配置 (Linear/TL/UL) 实例化单元
    3. 预处理载荷与约束 (展开 Set/Surface)
    4. 调用对应的求解器
    5. 简单的后处理 (位移提取)
    """

    # 信号定义
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    # 完成信号: (nodes, elements, disp, stress_mises, stress_tensor)
    finished_signal = pyqtSignal(dict, list, np.ndarray, np.ndarray, np.ndarray)
    error_signal = pyqtSignal(str)
    # 监控信号: 发送迭代状态信息 {time, dt, iter, residual, converged, increment}
    monitor_signal = pyqtSignal(dict)

    def __init__(self, inp_path, inp_data=None, material_props=None, solver_config=None):
        super().__init__()
        self.inp_path = inp_path
        self.inp_data_override = inp_data
        self.material_props = material_props or {"E": 70000.0, "nu": 0.3}
        
        # 接收 GUI 传来的配置，默认为 Linear
        self.solver_config = solver_config or {"type": "Linear"}

    def _log(self, msg: str):
        """线程安全日志"""
        try:
            self.log_signal.emit(msg)
        finally:
            print(msg)

    def run(self):
        try:
            # 检查中断请求
            if self.isInterruptionRequested():
                return
            
            self.progress_signal.emit(5)
            analysis_type = self.solver_config.get("type", "Linear")
            self._log(f"Starting Analysis. Formulation: {analysis_type}")
            
            # --- 1. 数据解析 ---
            if self.inp_data_override is not None:
                inp_data = copy.deepcopy(self.inp_data_override)
                self._log("Using in-memory INP data")
            else:
                self._log(f"Reading file: {self.inp_path}")
                parser = InpParser()
                inp_data = parser.read(self.inp_path)

            # 检查中断请求
            if self.isInterruptionRequested():
                return

            self.progress_signal.emit(15)
            
            # --- 2. 构建材料对象 (使用工厂模式) ---
            # 优先使用 INP 文件中定义的材料，否则使用 GUI 传入的参数
            material = None
            is_plastic_material = False
            
            if inp_data.get('materials'):
                # 使用 INP 中第一个材料定义
                mat_name, mat_props = next(iter(inp_data['materials'].items()))
                
                # 合并 GUI 传入的参数作为备选
                if mat_props.get('E') is None:
                    mat_props['E'] = self.material_props.get("E", 70000.0)
                if mat_props.get('nu') is None:
                    mat_props['nu'] = self.material_props.get("nu", 0.3)
                
                try:
                    # 线性分析：强制使用弹性材料 (忽略 INP 中的塑性数据)
                    if analysis_type == "Linear":
                        material = MaterialFactory.create_elastic(
                            mat_props['E'],
                            mat_props['nu']
                        )
                        self._log(f"Material '{mat_name}' (elastic only) created for Linear analysis")
                    else:
                        # 非线性分析：使用完整材料定义
                        material = MaterialFactory.create(mat_name, mat_props)
                        is_plastic_material = mat_props.get('plastic') is not None
                        self._log(f"Material '{mat_name}' created from INP file")
                        
                        if is_plastic_material:
                            self._log(f"  -> Plastic material (yield={mat_props['plastic']['yield_stress']})")
                            
                except ValueError as e:
                    self._log(f"Warning: {e}. Using GUI parameters instead.")
                    material = None
            
            # 如果没有从 INP 获取材料，使用 GUI 参数
            if material is None:
                material = MaterialFactory.create_elastic(
                    self.material_props.get("E", 70000.0),
                    self.material_props.get("nu", 0.3)
                )
            
            nodes_map = {nid: Node(nid, *coords) for nid, coords in inp_data['nodes'].items()}
            num_nodes = len(nodes_map)
            
            # --- 3. 实例化单元 (根据类型分支) ---
            elements_list = []
            
            if analysis_type == "Linear":
                # 标准线性单元
                for eid, node_ids in inp_data['elements'].items():
                    if self.isInterruptionRequested():
                        return
                    elem_nodes = [nodes_map[nid] for nid in node_ids]
                    elements_list.append(C3D8Element(eid, elem_nodes, material))
                    
            elif analysis_type == "TL":
                # Total Lagrangian 单元 (传入材料对象)
                for eid, node_ids in inp_data['elements'].items():
                    if self.isInterruptionRequested():
                        return
                    elem_nodes = [nodes_map[nid] for nid in node_ids]
                    elements_list.append(C3D8_TL(eid, elem_nodes, material))
                    
            elif analysis_type == "UL":
                # Updated Lagrangian 单元 (传入材料对象)
                for eid, node_ids in inp_data['elements'].items():
                    if self.isInterruptionRequested():
                        return
                    elem_nodes = [nodes_map[nid] for nid in node_ids]
                    elements_list.append(C3D8_UL(eid, elem_nodes, material))
            
            # 检查中断请求
            if self.isInterruptionRequested():
                return
            
            self._log(f"Model created: {num_nodes} Nodes, {len(elements_list)} Elements")
            self.progress_signal.emit(25)

            # --- 4. 预处理约束与载荷 (展开 Set/Surface 为纯 Node ID) ---
            # 这一步对于 Linear 和 Nonlinear 都是必须的，因为 Solver 只认 Node ID
            
            # 4.1 展开约束
            expanded_constraints = []
            for cons in inp_data['constraints']:
                if 'set_name' in cons:
                    sname = cons['set_name']
                    if sname in inp_data.get('nsets', {}):
                        nids = inp_data['nsets'][sname]
                        for nid in nids:
                            expanded_constraints.append({
                                'node_id': nid, 'dof': cons['dof'], 'value': cons['value']
                            })
                    else:
                        self._log(f"Warning: Constraint NSet '{sname}' not found.")
                elif 'node_id' in cons:
                    expanded_constraints.append(cons)

            # 4.2 展开载荷 (注意：inp_reader 已经把 Surface Load 展开成了 node_id 载荷条目)
            clean_loads = []
            for load in inp_data['loads']:
                # 忽略 surface 定义条目本身，只取已被 inp_reader 转换好的 node_id 条目
                if 'surface_name' in load and 'node_id' not in load:
                    continue 
                
                if 'set_name' in load:
                    sname = load['set_name']
                    if sname in inp_data.get('nsets', {}):
                        nids = inp_data['nsets'][sname]
                        for nid in nids:
                            clean_loads.append({
                                'node_id': nid, 'dof': load['dof'], 'value': load['value']
                            })
                    else:
                        self._log(f"Warning: Load NSet '{sname}' not found.")
                elif 'node_id' in load:
                    clean_loads.append(load)

            # --- 5. 执行求解 (分支) ---
            U_global = None
            
            # 检查中断请求
            if self.isInterruptionRequested():
                return
            
            if analysis_type == "Linear":
                # === 线性求解流程 ===
                self._log("Assembling linear stiffness matrix...")
                assembler = GlobalAssembler(elements_list, num_nodes)
                K_global = assembler.assemble()
                
                # 检查中断请求
                if self.isInterruptionRequested():
                    return
                
                self.progress_signal.emit(50)
                
                # 组装线性载荷向量 F_global
                F_global = np.zeros(num_nodes * 3)
                sorted_nids = sorted(nodes_map.keys())
                nid_to_idx = {nid: i for i, nid in enumerate(sorted_nids)}
                
                for ld in clean_loads:
                    if self.isInterruptionRequested():
                        return
                    if ld['node_id'] in nid_to_idx:
                        idx = nid_to_idx[ld['node_id']]
                        # 简单的 += 叠加
                        F_global[idx * 3 + ld['dof']] += ld['value']
                
                # 检查中断请求
                if self.isInterruptionRequested():
                    return
                
                self._log("Solving linear system (PCG)...")
                solver = LinearSolver(K_global, F_global)
                U_global = solver.solve(expanded_constraints, method='cg')
                
            else:
                # === 非线性求解流程 (TL/UL) ===
                self._log(f"Initializing Nonlinear Solver ({analysis_type})...")
                
                # 实例化非线性求解器
                nl_solver = NonlinearSolver(
                    elements_list,
                    num_nodes,
                    expanded_constraints,
                    clean_loads,
                    config=self.solver_config
                )
                nl_solver.set_log_callback(self._log)
                # 设置监控回调，将监控数据通过信号发送
                nl_solver.set_monitor_callback(lambda data: self.monitor_signal.emit(data))
                # 设置中断回调，用于 Kill Job 功能
                nl_solver.set_interrupt_callback(self.isInterruptionRequested)
                
                # 运行迭代求解
                # 进度回调直接连接到 Worker 的 signal
                U_global = nl_solver.solve(progress_callback=self.progress_signal.emit)

            # 检查中断请求
            if self.isInterruptionRequested():
                return

            self.progress_signal.emit(90)
            
            # --- 6. 后处理 (结果整合) ---
            self._log("Post-processing results...")
            
            disp_vectors = U_global.reshape((num_nodes, 3))
            
            # 应力恢复 (Stress Recovery)
            # 注意：目前的非线性单元(TL/UL)为了性能，没有存储积分点应力
            # 为了防止报错，非线性模式下暂不计算应力，或返回零矩阵
            # 线性模式下保持原有逻辑
            
            stress_mises = np.zeros(num_nodes)
            stress_components = np.zeros((num_nodes, 6))
            
            if analysis_type == "Linear":
                self._log("Recovering linear stress fields...")
                node_stress_accum = np.zeros((num_nodes, 7)) # 6 comp + weight
                # 线性单元使用 Quadrature 模块
                local_gauss, gauss_weights = Quadrature.get_points(order=2)
                sorted_nids = sorted(nodes_map.keys())
                nid_to_idx = {nid: i for i, nid in enumerate(sorted_nids)}

                for elem in elements_list:
                    if self.isInterruptionRequested():
                        return
                    u_elem = U_global[elem.get_dof_indices()]
                    # 简化外推：计算积分点应力，平均分配给节点
                    for i, xi in enumerate(local_gauss):
                        for j, eta in enumerate(local_gauss):
                            for k, zeta in enumerate(local_gauss):
                                if self.isInterruptionRequested():
                                    return
                                B, _ = elem._calc_B_matrix(xi, eta, zeta)
                                stress = material.D_matrix @ (B @ u_elem)
                                weight = gauss_weights[i] * gauss_weights[j] * gauss_weights[k]
                                
                                for node in elem.nodes:
                                    idx = nid_to_idx[node.id]
                                    node_stress_accum[idx, :6] += stress.flatten() * weight / 8
                                    node_stress_accum[idx, 6] += weight / 8
                
                # 平均化
                counts = node_stress_accum[:, 6]
                counts[counts==0] = 1.0
                stress_components = node_stress_accum[:, :6] / counts[:, np.newaxis]
                
                # 计算 Von Mises
                visualizer = FEMVisualizer()
                stress_mises = visualizer.calc_von_mises(stress_components)
            else:
                # === 非线性应力恢复 (使用求解器接口) ===
                # 调用 NonlinearSolver.recover_nodal_stresses()，使用正确的物理公式
                # TL: σ = (1/J) * F * S * F^T (St. Venant-Kirchhoff)
                # UL: σ = (μ/J)(b - I) + (λ/J)ln(J)I (Neo-Hookean)
                self._log("Recovering Cauchy stress for nonlinear elements...")
                stress_mises, stress_components = nl_solver.recover_nodal_stresses(U_global)

            self.progress_signal.emit(100)
            self.finished_signal.emit(nodes_map, elements_list, disp_vectors, stress_mises, stress_components)
            self._log("Job Completed.")

        except Exception as e:
            # 如果是中断请求导致的异常，不记录为错误
            if not self.isInterruptionRequested():
                self._log(f"CRITICAL ERROR: {str(e)}")
                import traceback
                traceback.print_exc()
                self.error_signal.emit(str(e))

# ParseWorker 保持不变，无需修改
class ParseWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_parse = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, inp_path):
        super().__init__()
        self.inp_path = inp_path

    def run(self):
        try:
            self.progress_signal.emit(5)
            self.log_signal.emit(f"Parsing INP file: {self.inp_path}")
            parser = InpParser()
            data = parser.read(self.inp_path)
            self.progress_signal.emit(100)
            self.finished_parse.emit(data)
        except Exception as e:
            self.error_signal.emit(str(e))