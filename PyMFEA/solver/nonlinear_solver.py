import numpy as np
import time
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
from solver.assembler import GlobalAssembler

class NonlinearSolver:
    """
    通用非线性求解器 (Sparse Matrix Version)
    
    特性：
    1. 使用 scipy.sparse 处理大型稀疏矩阵，逻辑与 assembler.py 保持一致
    2. 自动时间步长控制 (Auto Time Stepping)
    3. Newton-Raphson 迭代
    """
    
    def __init__(self, elements, num_nodes, constraints, loads_data, config=None):
        """
        Args:
            elements: 单元对象列表
            num_nodes: 节点总数
            constraints: 约束列表 (已展开为节点ID)
            loads_data: 载荷列表 (已展开为节点ID)
            config: 配置字典 (total_time, initial_dt, max_iter, tolerance)
        """
        self.elements = elements
        self.num_nodes = num_nodes
        self.num_dofs = num_nodes * 3
        
        # 边界与载荷
        self.constraints = constraints
        self.loads_data = loads_data
        
        # 配置 (针对塑性问题优化的默认值)
        self.config = config or {
            "total_time": 1.0, 
            "initial_dt": 0.02,   # 较小初始步长，适合塑性
            "max_iter": 30,       # 增加迭代次数
            "tolerance": 1e-4     # 适中的容差
        }
        
        # 状态量 (当前收敛的总位移)
        self.u_current = np.zeros(self.num_dofs)
        self.log_callback = print
        self.monitor_callback = None  # 监控回调函数
        self.check_interrupt = None   # 中断检查回调

    def set_log_callback(self, callback):
        self.log_callback = callback
    
    def set_monitor_callback(self, callback):
        """设置监控回调函数，用于实时发送迭代状态"""
        self.monitor_callback = callback
    
    def set_interrupt_callback(self, callback):
        """设置中断检查回调，用于 Kill Job 功能"""
        self.check_interrupt = callback

    def _build_load_vector(self, factor):
        """构建当前时间步的外力向量 F_ext = Load * factor"""
        F_ext = np.zeros(self.num_dofs)
        
        for load in self.loads_data:
            # 假设输入数据的 node_id 是 1-based
            nid = load['node_id']
            dof = load['dof']
            val = load['value']
            
            # 映射到矩阵索引 (0-based)
            idx = (nid - 1) * 3 + dof
            if 0 <= idx < self.num_dofs:
                F_ext[idx] += val * factor
        return F_ext

    def _line_search(self, u_base, du, target_load, assembler, res_norm_old, max_ls_iter=5):
        """
        回溯线搜索 (Backtracking Line Search)
        
        寻找步长 α 使得 ||R(u + α*du)|| < ||R(u)||
        
        Args:
            u_base: 当前位移
            du: Newton 方向
            target_load: 目标载荷向量
            assembler: 全局组装器
            res_norm_old: 当前残差范数
            max_ls_iter: 最大线搜索迭代次数
            
        Returns:
            alpha: 最优步长 (0 < α <= 1)
            res_norm_new: 新残差范数
            success: 是否成功降低残差
        """
        alpha = 1.0
        beta = 0.5  # 步长缩减因子
        c = 1e-4    # Armijo 条件参数
        
        for ls_iter in range(max_ls_iter):
            # 试探新位移
            u_trial = u_base + alpha * du
            
            # 重新计算内力
            def compute_element(elem, u_current):
                return elem.compute_element(u_current)
            
            K_new, F_int_new, failed = assembler.assemble_generic(
                compute_element, 
                u_current=u_trial
            )
            
            if failed:
                alpha *= beta
                continue
            
            # 计算新残差
            R_new = target_load - F_int_new
            
            # 边界条件处理
            from solver.boundary_conditions import BoundaryConditionHandler
            _, R_new = BoundaryConditionHandler.apply_penalty_for_residual(
                K_new, R_new, self.constraints, 
                penalty_multiplier=1e9, is_sparse=True
            )
            
            res_norm_new = np.linalg.norm(R_new)
            
            # Armijo 条件: 残差是否足够减小
            if res_norm_new < res_norm_old * (1 - c * alpha):
                return alpha, res_norm_new, True
            
            # 缩小步长继续搜索
            alpha *= beta
        
        # 线搜索失败，返回最小步长
        return alpha, res_norm_new, False

    def solve(self, progress_callback=None):
        # 1. 提取配置
        end_time = self.config.get("total_time", 1.0)
        dt = self.config.get("initial_dt", 0.05)
        max_iter = int(self.config.get("max_iter", 15))
        tol = self.config.get("tolerance", 1e-3)
        
        current_time = 0.0
        min_dt = 1e-6
        
        # 创建全局组装器实例（复用线性求解器的组装逻辑）
        assembler = GlobalAssembler(self.elements, self.num_nodes)
        
        self.log_callback(f"{'TIME':<8} | {'dt':<8} | {'ITER':<5} | {'RESIDUAL':<12} | {'STATUS'}")
        self.log_callback("-" * 65)

        # 2. 时间增量循环
        while current_time < end_time:
            # 步长修正
            if current_time + dt > end_time: 
                dt = end_time - current_time + 1e-10
            
            target_load = self._build_load_vector(current_time + dt)
            converged = False
            du_accum = np.zeros(self.num_dofs) # 当前步内的累积位移增量
            
            # 3. Newton-Raphson 迭代
            for iter_i in range(max_iter):
                # === 检查中断请求 ===
                if self.check_interrupt and self.check_interrupt():
                    self.log_callback("\n*** Job terminated by user ***")
                    return self.u_current
                
                u_trial = self.u_current + du_accum
                
                # --- A. 稀疏矩阵组装 (使用通用组装器) ---
                # 定义非线性单元计算回调函数
                def compute_nonlinear_element(elem, u_current):
                    """
                    回调函数：计算单元切线刚度矩阵和内力向量
                    Returns: (Ke, Fe, failed)
                    """
                    return elem.compute_element(u_current)
                
                # 调用通用组装器
                K_sys, F_int_sys, assembly_failed = assembler.assemble_generic(
                    compute_nonlinear_element, 
                    u_current=u_trial
                )
                
                if assembly_failed:
                    self.log_callback(f"{current_time:.4f} | {dt:.4f} | {iter_i} | -- | Element Bad")
                    break

                # --- B. 计算残差 ---
                R = target_load - F_int_sys
                
                # --- C. 边界条件处理 (使用统一的 BoundaryConditionHandler) ---
                from solver.boundary_conditions import BoundaryConditionHandler
                
                # 非线性迭代使用 apply_penalty_for_residual：
                # - 残差 R[idx] = 0（约束自由度没有不平衡力）
                # - 刚度 K[idx,idx] += α（确保 du[idx] ≈ 0）
                K_sys, R = BoundaryConditionHandler.apply_penalty_for_residual(
                    K_sys,
                    R,
                    self.constraints,
                    penalty_multiplier=1e9,
                    is_sparse=True
                )

                # --- D. 收敛性检查 ---
                res_norm = np.linalg.norm(R)
                
                # 发送监控数据
                if self.monitor_callback:
                    monitor_data = {
                        'time': current_time + dt,
                        'dt': dt,
                        'iter': iter_i,
                        'residual': res_norm,
                        'converged': False,
                        'increment': int(current_time / dt) if dt > 0 else 0
                    }
                    self.monitor_callback(monitor_data)
                
                # 格式化输出
                status_str = "..."
                if iter_i == 0: 
                    self.log_callback(f"{current_time+dt:.4f}   | {dt:.4f}   | {iter_i:<5} | {res_norm:.4e}   | Start")
                
                if res_norm < tol:
                    converged = True
                    status_str = "Converged"
                    self.log_callback(f"{current_time+dt:.4f}   | {dt:.4f}   | {iter_i:<5} | {res_norm:.4e}   | \033[92m{status_str}\033[0m")
                    # 发送收敛状态
                    if self.monitor_callback:
                        monitor_data['converged'] = True
                        self.monitor_callback(monitor_data)
                    break
                else:
                    self.log_callback(f"{current_time+dt:.4f}   | {dt:.4f}   | {iter_i:<5} | {res_norm:.4e}   | {status_str}")

                # --- E. 稀疏线性求解 ---
                try:
                    # 使用 scipy.sparse.linalg.spsolve
                    du = spsolve(K_sys, R)
                except Exception as e:
                    self.log_callback(f"Linear Solver Error: {str(e)}")
                    break
                
                # 发散保护
                if np.max(np.abs(du)) > 1e6:
                    self.log_callback("Divergence detected (large du)")
                    break
                
                # --- F. 线搜索 (新增) ---
                alpha, res_after_ls, ls_success = self._line_search(
                    u_trial, du, target_load, assembler, res_norm, max_ls_iter=5
                )
                
                # 使用线搜索步长更新位移
                du_accum += alpha * du
                
                # 如果线搜索失败且残差增大很多，考虑提前退出
                if not ls_success and res_after_ls > res_norm * 2:
                    self.log_callback(f"  Line search failed, α={alpha:.3f}")
                elif alpha < 1.0:
                    # 只在步长被缩减时输出
                    pass  # self.log_callback(f"  α={alpha:.3f}")

            # 4. 步长控制
            if converged:
                self.u_current += du_accum
                current_time += dt
                
                # === 提交积分点状态 (塑性历史锁定) ===
                for elem in self.elements:
                    if hasattr(elem, 'commit_state'):
                        elem.commit_state()
                
                if progress_callback:
                    progress_callback(int((current_time / end_time) * 100))
                
                if iter_i < 5: dt *= 1.5
                if current_time + dt > end_time: dt = end_time - current_time + 1e-10
                
                if abs(current_time - end_time) < 1e-6:
                    break
            else:
                dt *= 0.5
                if dt < min_dt:
                    self.log_callback("Step too small, aborting.")
                    break
                self.log_callback(f">>> Cutback: dt = {dt:.4e}")
        
        return self.u_current

    def recover_nodal_stresses(self, U_global):
        """
        从收敛的位移场恢复节点应力
        
        策略：
        1. 遍历每个单元，调用 elem.calculate_cauchy_stress(u_elem)
        2. 将单元中心点应力平均分配给 8 个节点 (Accumulate & Average)
        3. 计算 Von Mises 应力
        
        Args:
            U_global: 全局位移向量 (num_dofs,)
            
        Returns:
            stress_mises: Von Mises 应力 (num_nodes,)
            stress_components: 应力分量 (num_nodes, 6)
        """
        # 初始化累加器: [σxx, σyy, σzz, τyz, τxz, τxy, count]
        node_stress_accum = np.zeros((self.num_nodes, 7))
        
        for elem in self.elements:
            # 提取单元位移
            idx = elem.get_dof_indices()
            u_elem = U_global[idx]
            
            # 调用单元应力计算方法 (返回 Voigt 向量)
            sigma_voigt = elem.calculate_cauchy_stress(u_elem)
            
            # 将应力分配给单元的 8 个节点
            for node in elem.nodes:
                # Node ID 是 1-based，转换为 0-based 索引
                node_idx = node.id - 1
                if 0 <= node_idx < self.num_nodes:
                    node_stress_accum[node_idx, :6] += sigma_voigt
                    node_stress_accum[node_idx, 6] += 1.0
        
        # 平均化
        counts = node_stress_accum[:, 6]
        counts[counts == 0] = 1.0  # 避免除零
        stress_components = node_stress_accum[:, :6] / counts[:, np.newaxis]
        
        # 计算 Von Mises 应力
        # σ_vm = sqrt(σxx² + σyy² + σzz² - σxx*σyy - σyy*σzz - σzz*σxx + 3*(τxy² + τyz² + τxz²))
        sxx = stress_components[:, 0]
        syy = stress_components[:, 1]
        szz = stress_components[:, 2]
        tyz = stress_components[:, 3]
        txz = stress_components[:, 4]
        txy = stress_components[:, 5]
        
        stress_mises = np.sqrt(
            sxx**2 + syy**2 + szz**2 
            - sxx*syy - syy*szz - szz*sxx 
            + 3.0 * (txy**2 + tyz**2 + txz**2)
        )
        
        return stress_mises, stress_components