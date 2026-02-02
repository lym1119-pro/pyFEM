# 文件路径: PyMFEA/core/element_nonlinear.py
"""
重构后的非线性单元模块

关键变更:
1. 单元只计算变形梯度 F，不再预计算应变
2. 将 F 直接传递给材料接口，材料内部决定应变度量
3. 支持新的 FiniteStrainMaterial 接口和旧的 BaseMaterial 接口
"""

import numpy as np
from typing import Optional, Tuple
import copy

from core.materials import Material, StressResult


class C3D8_Nonlinear_Base:
    """
    非线性 C3D8 单元基类
    
    职责：
    1. 管理节点和材料属性
    2. 预计算高斯积分点和局部形状函数导数
    3. 管理积分点状态变量 (塑性历史)
    """
    
    def __init__(self, element_id: int, nodes: list, material):
        """
        Args:
            element_id: 单元 ID
            nodes: 8个节点对象列表
            material: 材料对象 (FiniteStrainMaterial 或 BaseMaterial)
        """
        self.id = element_id
        self.nodes = nodes
        self.material = material
        
        # 检查材料是否支持新接口
        self._use_new_interface = isinstance(material, Material)
        
        # 预计算 2x2x2 高斯积分点
        p = 1.0 / np.sqrt(3.0)
        self.gauss_points = [-p, p]

        # 预计算局部形状函数导数
        self.dN_dxi_local = []
        
        node_local = np.array([
            [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
            [-1, -1, 1],  [1, -1, 1],  [1, 1, 1],  [-1, 1, 1]
        ])
        
        for xi in self.gauss_points:
            for eta in self.gauss_points:
                for zeta in self.gauss_points:
                    dN = np.zeros((3, 8))
                    for i in range(8):
                        r, s, t = node_local[i]
                        dN[0, i] = 0.125 * r * (1 + s*eta) * (1 + t*zeta)
                        dN[1, i] = 0.125 * (1 + r*xi) * s * (1 + t*zeta)
                        dN[2, i] = 0.125 * (1 + r*xi) * (1 + s*eta) * t
                    self.dN_dxi_local.append(dN)
        
        # 积分点状态变量管理
        self._init_gp_states()
    
    def _init_gp_states(self):
        """初始化积分点状态"""
        if hasattr(self.material, 'create_initial_state'):
            self.gp_states_committed = [
                self.material.create_initial_state() for _ in range(8)
            ]
            self.gp_states_current = [
                self.material.create_initial_state() for _ in range(8)
            ]
        else:
            self.gp_states_committed = [None] * 8
            self.gp_states_current = [None] * 8
    
    def commit_state(self):
        """
        提交当前步的状态
        
        在时间步收敛后调用，将 current 状态深拷贝到 committed。
        """
        for gp_idx in range(8):
            state = self.gp_states_current[gp_idx]
            if state is not None and hasattr(state, 'clone'):
                self.gp_states_committed[gp_idx] = state.clone()
            elif state is not None:
                self.gp_states_committed[gp_idx] = copy.deepcopy(state)

    def get_dof_indices(self) -> np.ndarray:
        """获取单元对应的全局自由度索引"""
        dofs = []
        for node in self.nodes:
            start = (node.id - 1) * 3
            dofs.extend([start, start + 1, start + 2])
        return np.array(dofs, dtype=int)
    
    def _compute_deformation_gradient(self,
                                       u_ele: np.ndarray,
                                       dN_dX: np.ndarray) -> np.ndarray:
        """
        计算变形梯度 F
        
        F = I + ∂u/∂X
        
        Args:
            u_ele: 节点位移 (8, 3)
            dN_dX: 形函数对初始坐标的导数 (3, 8)
            
        Returns:
            F: 变形梯度 (3, 3)
        """
        du_dX = u_ele.T @ dN_dX.T  # (3, 3)
        return np.eye(3) + du_dX


class C3D8_TL(C3D8_Nonlinear_Base):
    """
    Total Lagrangian (TL) 格式单元 (重构版)
    
    - 参考构型：初始构型 (X)
    - 应力度量：2nd Piola-Kirchhoff Stress (S)
    - 关键变更：只计算 F，材料内部计算应变
    """
    
    def __init__(self, element_id: int, nodes: list, material):
        super().__init__(element_id, nodes, material)
        self.X_ref = np.array([n.coords for n in self.nodes])

    def compute_element(self, u_global: np.ndarray) -> Tuple[np.ndarray, np.ndarray, bool]:
        """
        计算单元切线刚度矩阵和内力向量
        
        Args:
            u_global: 全局位移向量
            
        Returns:
            K_tan: 切线刚度矩阵 (24x24)
            F_int: 内力向量 (24,)
            failed: 计算是否失败
        """
        idx = self.get_dof_indices()
        u_ele = u_global[idx].reshape(8, 3)
        
        K_tan = np.zeros((24, 24))
        F_int = np.zeros(24)
        
        for gp_idx in range(8):
            dN_dxi = self.dN_dxi_local[gp_idx]
            
            # 克隆上一步收敛的状态
            state_trial = None
            if self.gp_states_committed[gp_idx] is not None:
                state_trial = self.gp_states_committed[gp_idx].clone()
            
            # --- 运动学：只计算 F ---
            J0 = dN_dxi @ self.X_ref
            det_J0 = np.linalg.det(J0)
            
            if det_J0 <= 1e-12:
                return None, None, True
                
            inv_J0 = np.linalg.inv(J0)
            dN_dX = inv_J0 @ dN_dxi
            
            # 计算变形梯度 F
            F = self._compute_deformation_gradient(u_ele, dN_dX)
            
            # --- 本构关系：将 F 传递给材料 ---
            if self._use_new_interface:
                # 新接口：材料内部计算应变
                result = self.material.compute_stress(F, state=state_trial)
                S_voigt = result.stress
                D_tang = result.tangent
                # *** 关键修复：保存材料返回的更新后状态 ***
                self.gp_states_current[gp_idx] = result.state
            else:
                # 旧接口 (向后兼容)：单元计算应变
                E_tensor = 0.5 * (F.T @ F - np.eye(3))
                E_voigt = np.array([
                    E_tensor[0,0], E_tensor[1,1], E_tensor[2,2],
                    2*E_tensor[1,2], 2*E_tensor[0,2], 2*E_tensor[0,1]
                ])
                S_voigt, D_tang = self.material.compute_tl_stress(E_voigt, state=state_trial)
                # 旧接口：保存原状态
                self.gp_states_current[gp_idx] = state_trial
            
            # 还原应力张量
            S_tensor = np.array([
                [S_voigt[0], S_voigt[5], S_voigt[4]],
                [S_voigt[5], S_voigt[1], S_voigt[3]],
                [S_voigt[4], S_voigt[3], S_voigt[2]]
            ])
            
            # --- 刚度矩阵组装 ---
            B_NL = self._build_B_matrix(F, dN_dX)
            dV = det_J0
            
            # 材料刚度
            K_mat = B_NL.T @ D_tang @ B_NL * dV
            
            # 内力
            F_int += B_NL.T @ S_voigt * dV
            
            # 几何刚度
            K_geo = self._build_geometric_stiffness(dN_dX, S_tensor, dV)
            
            K_tan += K_mat + K_geo
            
        return K_tan, F_int, False
    
    def _build_B_matrix(self, F: np.ndarray, dN_dX: np.ndarray) -> np.ndarray:
        """构造非线性应变-位移矩阵 B_NL (6x24)"""
        B_NL = np.zeros((6, 24))
        
        for i in range(8):
            dNi = dN_dX[:, i]
            col = 3 * i
            
            # 正应变项
            B_NL[0, col:col+3] = F[0,0]*dNi[0], F[1,0]*dNi[0], F[2,0]*dNi[0]
            B_NL[1, col:col+3] = F[0,1]*dNi[1], F[1,1]*dNi[1], F[2,1]*dNi[1]
            B_NL[2, col:col+3] = F[0,2]*dNi[2], F[1,2]*dNi[2], F[2,2]*dNi[2]
            
            # 剪应变项
            B_NL[3, col:col+3] = (F[0,1]*dNi[2] + F[0,2]*dNi[1]), \
                                 (F[1,1]*dNi[2] + F[1,2]*dNi[1]), \
                                 (F[2,1]*dNi[2] + F[2,2]*dNi[1])
            B_NL[4, col:col+3] = (F[0,0]*dNi[2] + F[0,2]*dNi[0]), \
                                 (F[1,0]*dNi[2] + F[1,2]*dNi[0]), \
                                 (F[2,0]*dNi[2] + F[2,2]*dNi[0])
            B_NL[5, col:col+3] = (F[0,0]*dNi[1] + F[0,1]*dNi[0]), \
                                 (F[1,0]*dNi[1] + F[1,1]*dNi[0]), \
                                 (F[2,0]*dNi[1] + F[2,1]*dNi[0])
        
        return B_NL
    
    def _build_geometric_stiffness(self,
                                    dN_dX: np.ndarray,
                                    S_tensor: np.ndarray,
                                    dV: float) -> np.ndarray:
        """构造几何刚度矩阵 K_geo (24x24)"""
        k_geo_small = np.zeros((8, 8))
        
        for i in range(8):
            for j in range(8):
                k_geo_small[i, j] = dN_dX[:, i].T @ S_tensor @ dN_dX[:, j]
        
        K_geo = np.kron(k_geo_small, np.eye(3)) * dV
        return K_geo
    
    def calculate_cauchy_stress(self, u_elem: np.ndarray) -> np.ndarray:
        """
        计算柯西应力 (后处理)
        
        从已提交的积分点状态读取 PK2 应力，push-forward 到柯西应力
        """
        sigma_accum = np.zeros(6)
        count = 0
        
        for gp_idx in range(8):
            state = self.gp_states_committed[gp_idx]
            
            # 计算运动学
            u_ele = u_elem.reshape(8, 3)
            dN_dxi = self.dN_dxi_local[gp_idx]
            J0 = dN_dxi @ self.X_ref
            det_J0 = np.linalg.det(J0)
            
            if det_J0 <= 1e-12:
                continue
            
            inv_J0 = np.linalg.inv(J0)
            dN_dX = inv_J0 @ dN_dxi
            F = self._compute_deformation_gradient(u_ele, dN_dX)
            J = np.linalg.det(F)
            
            if J <= 1e-12:
                continue
            
            # 获取 PK2 应力
            if state is not None and hasattr(state, 'stress') and state.stress is not None:
                S_voigt = state.stress
            else:
                # 重新计算
                if self._use_new_interface:
                    result = self.material.compute_stress(F, state=None)
                    S_voigt = result.stress
                else:
                    E_tensor = 0.5 * (F.T @ F - np.eye(3))
                    E_voigt = np.array([
                        E_tensor[0,0], E_tensor[1,1], E_tensor[2,2],
                        2*E_tensor[1,2], 2*E_tensor[0,2], 2*E_tensor[0,1]
                    ])
                    S_voigt, _ = self.material.compute_tl_stress(E_voigt, state=None)
            
            # Push-forward: σ = (1/J) F S F^T
            S_tensor = np.array([
                [S_voigt[0], S_voigt[5], S_voigt[4]],
                [S_voigt[5], S_voigt[1], S_voigt[3]],
                [S_voigt[4], S_voigt[3], S_voigt[2]]
            ])
            sigma_tensor = (1.0 / J) * (F @ S_tensor @ F.T)
            
            sigma_voigt = np.array([
                sigma_tensor[0,0], sigma_tensor[1,1], sigma_tensor[2,2],
                sigma_tensor[1,2], sigma_tensor[0,2], sigma_tensor[0,1]
            ])
            
            sigma_accum += sigma_voigt
            count += 1
        
        return sigma_accum / count if count > 0 else np.zeros(6)


class C3D8_UL(C3D8_Nonlinear_Base):
    """
    Updated Lagrangian (UL) 格式单元 (重构版)
    
    - 参考构型：当前构型 (x = X + u)
    - 应力度量：Cauchy Stress (σ)
    - 关键变更：只计算 F，材料内部计算应变
    """
    
    def __init__(self, element_id: int, nodes: list, material):
        super().__init__(element_id, nodes, material)
        self.X_ref = np.array([n.coords for n in self.nodes])

    def compute_element(self, u_global: np.ndarray) -> Tuple[np.ndarray, np.ndarray, bool]:
        """UL 格式的核心计算"""
        idx = self.get_dof_indices()
        u_ele = u_global[idx].reshape(8, 3)
        
        # 更新当前坐标
        x_curr = self.X_ref + u_ele
        
        K_tan = np.zeros((24, 24))
        F_int = np.zeros(24)
        
        for gp_idx in range(8):
            dN_dxi = self.dN_dxi_local[gp_idx]
            
            # 克隆上一步状态
            state_trial = None
            if self.gp_states_committed[gp_idx] is not None:
                state_trial = self.gp_states_committed[gp_idx].clone()
            
            # --- 运动学 ---
            # 初始构型雅可比 (用于计算 F)
            J_ref = dN_dxi @ self.X_ref
            try:
                inv_J_ref = np.linalg.inv(J_ref)
            except np.linalg.LinAlgError:
                return None, None, True
            
            dN_dX = inv_J_ref @ dN_dxi
            
            # 变形梯度 F
            F = self._compute_deformation_gradient(u_ele, dN_dX)
            J = np.linalg.det(F)
            
            if J <= 1e-6:
                return None, None, True
            
            # 当前构型雅可比
            J_cur = dN_dxi @ x_curr
            det_J_cur = np.linalg.det(J_cur)
            inv_J_cur = np.linalg.inv(J_cur)
            dN_dx = inv_J_cur @ dN_dxi
            
            # --- 本构关系：将 F 传递给材料 ---
            if self._use_new_interface:
                result = self.material.compute_stress(F, state=state_trial)
                sig_voigt = result.stress
                D_tang = result.tangent
                # *** 关键修复：保存材料返回的更新后状态 ***
                self.gp_states_current[gp_idx] = result.state
            else:
                # 旧接口 (向后兼容)
                sig_voigt, D_tang = self.material.compute_ul_stress(F, J, state=state_trial)
                # 旧接口：保存原状态
                self.gp_states_current[gp_idx] = state_trial
            
            # 还原应力张量
            sigma = np.array([
                [sig_voigt[0], sig_voigt[5], sig_voigt[4]],
                [sig_voigt[5], sig_voigt[1], sig_voigt[3]],
                [sig_voigt[4], sig_voigt[3], sig_voigt[2]]
            ])
            
            # --- 刚度矩阵组装 ---
            B = self._build_B_matrix_linear(dN_dx)
            dV = det_J_cur
            
            # 内力
            F_int += B.T @ sig_voigt * dV
            
            # 材料刚度
            K_mat = B.T @ D_tang @ B * dV
            
            # 几何刚度
            K_geo = self._build_geometric_stiffness(dN_dx, sigma, dV)
            
            K_tan += K_mat + K_geo
            
        return K_tan, F_int, False
    
    def _build_B_matrix_linear(self, dN_dx: np.ndarray) -> np.ndarray:
        """构造线性 B 矩阵 (基于当前坐标)"""
        B = np.zeros((6, 24))
        
        for i in range(8):
            col = 3 * i
            dN = dN_dx[:, i]
            
            B[0, col]   = dN[0]
            B[1, col+1] = dN[1]
            B[2, col+2] = dN[2]
            B[3, col+1] = dN[2]; B[3, col+2] = dN[1]
            B[4, col]   = dN[2]; B[4, col+2] = dN[0]
            B[5, col]   = dN[1]; B[5, col+1] = dN[0]
        
        return B
    
    def _build_geometric_stiffness(self,
                                    dN_dx: np.ndarray,
                                    sigma: np.ndarray,
                                    dV: float) -> np.ndarray:
        """构造几何刚度矩阵"""
        k_geo_small = np.zeros((8, 8))
        
        for i in range(8):
            for j in range(8):
                k_geo_small[i, j] = dN_dx[:, i].T @ sigma @ dN_dx[:, j]
        
        return np.kron(k_geo_small, np.eye(3)) * dV
    
    def calculate_cauchy_stress(self, u_elem: np.ndarray) -> np.ndarray:
        """计算柯西应力 (后处理)"""
        sigma_accum = np.zeros(6)
        count = 0
        
        for gp_idx in range(8):
            state = self.gp_states_committed[gp_idx]
            
            # 优先从状态读取
            if state is not None and hasattr(state, 'stress') and state.stress is not None:
                sigma_accum += state.stress
                count += 1
            else:
                # 重新计算
                u_ele = u_elem.reshape(8, 3)
                dN_dxi = self.dN_dxi_local[gp_idx]
                
                J_ref = dN_dxi @ self.X_ref
                try:
                    inv_J_ref = np.linalg.inv(J_ref)
                except np.linalg.LinAlgError:
                    continue
                
                dN_dX = inv_J_ref @ dN_dxi
                F = self._compute_deformation_gradient(u_ele, dN_dX)
                J = np.linalg.det(F)
                
                if J <= 1e-6:
                    continue
                
                if self._use_new_interface:
                    result = self.material.compute_stress(F, state=None)
                    sigma_voigt = result.stress
                else:
                    sigma_voigt, _ = self.material.compute_ul_stress(F, J, state=None)
                
                sigma_accum += sigma_voigt
                count += 1
        
        return sigma_accum / count if count > 0 else np.zeros(6)