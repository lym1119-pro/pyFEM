# 文件路径: PyMFEA/solver/boundary_conditions.py
"""
统一的边界条件处理模块

提供一致的罚函数法实现，用于线性和非线性求解器。
"""
import numpy as np
import scipy.sparse as sp


class BoundaryConditionHandler:
    """
    统一的边界条件处理器
    
    使用罚函数法应用边界条件，确保线性和非线性求解器的一致性。
    """
    
    @staticmethod
    def apply_penalty_method(K, F_or_R, constraints, penalty_multiplier=1e9, is_sparse=True):
        """
        使用罚函数法应用边界条件
        
        罚函数法原理：
        - 对于约束自由度 i，修改刚度矩阵对角元素：K[i,i] += α
        - 修改载荷向量：F[i] += α * prescribed_value
        - 罚因子 α = max(diag(K)) * penalty_multiplier
        
        Args:
            K: 刚度矩阵 (scipy.sparse matrix 或 numpy array)
            F_or_R: 载荷向量或残差向量 (numpy array)
            constraints (list of dict): 约束列表
                格式: {'node_id': int, 'dof': int, 'value': float}
                dof: 0=x, 1=y, 2=z
            penalty_multiplier (float): 罚因子倍数，默认 1e9
            is_sparse (bool): K 是否为稀疏矩阵
        
        Returns:
            K_modified: 修改后的刚度矩阵（保持原格式）
            F_modified: 修改后的载荷/残差向量
        
        Raises:
            ValueError: 如果约束超出矩阵范围
        """
        # 1. 计算自适应罚因子
        if is_sparse:
            max_diag = np.max(np.abs(K.diagonal()))
            # 转换为 LIL 格式以便修改
            K_mod = K.tolil()
        else:
            max_diag = np.max(np.abs(np.diag(K)))
            K_mod = K.copy()
        
        alpha = max_diag * penalty_multiplier
        F_mod = F_or_R.copy()
        
        # 2. 应用约束
        for cons in constraints:
            node_id = cons['node_id']
            dof = cons['dof']
            val = cons.get('value', 0.0)
            
            # 计算全局自由度索引
            # 假设节点 ID 从 1 开始
            row_idx = (node_id - 1) * 3 + dof
            
            # 边界检查
            if row_idx >= K.shape[0]:
                raise ValueError(
                    f"Constraint out of bounds: Node {node_id} DOF {dof} "
                    f"(index {row_idx} >= matrix size {K.shape[0]})"
                )
            
            # 修改刚度矩阵对角元素
            K_mod[row_idx, row_idx] += alpha
            
            # 修改载荷/残差向量
            F_mod[row_idx] += alpha * val
        
        # 3. 转换回原格式
        if is_sparse:
            K_mod = K_mod.tocsr()
        
        return K_mod, F_mod
    
    @staticmethod
    def apply_penalty_for_residual(K, R, constraints, penalty_multiplier=1e9, is_sparse=True):
        """
        对残差方程应用罚函数法边界条件（非线性求解器专用）
        
        与 apply_penalty_method 的区别：
        - apply_penalty_method: 用于线性求解，F[i] += α * val
        - apply_penalty_for_residual: 用于非线性迭代，R[i] = 0
        
        非线性迭代中，约束自由度的修正量 du 应为 0：
        - 设置 R[idx] = 0（无不平衡力）
        - 设置 K[idx,idx] += α（确保 du[idx] ≈ 0）
        
        Args:
            K: 切线刚度矩阵 (scipy.sparse matrix)
            R: 残差向量 (numpy array)
            constraints: 约束列表
            penalty_multiplier: 罚因子倍数
            is_sparse: K 是否为稀疏矩阵
        
        Returns:
            K_modified, R_modified
        """
        if is_sparse:
            max_diag = np.max(np.abs(K.diagonal()))
            K_mod = K.tolil()
        else:
            max_diag = np.max(np.abs(np.diag(K)))
            K_mod = K.copy()
        
        alpha = max_diag * penalty_multiplier
        R_mod = R.copy()
        
        for cons in constraints:
            node_id = cons['node_id']
            dof = cons['dof']
            
            row_idx = (node_id - 1) * 3 + dof
            
            if row_idx >= K.shape[0]:
                continue
            
            # 关键区别：残差设为 0，而不是加上 alpha * val
            R_mod[row_idx] = 0.0
            K_mod[row_idx, row_idx] += alpha
        
        if is_sparse:
            K_mod = K_mod.tocsr()
        
        return K_mod, R_mod
    
    @staticmethod
    def validate_constraints(constraints, num_nodes):
        """
        验证约束列表的有效性
        
        Args:
            constraints (list of dict): 约束列表
            num_nodes (int): 节点总数
        
        Returns:
            list: 有效的约束列表
            list: 无效约束的错误信息
        """
        valid_constraints = []
        errors = []
        
        for i, cons in enumerate(constraints):
            # 检查必需字段
            if 'node_id' not in cons:
                errors.append(f"Constraint {i}: missing 'node_id'")
                continue
            
            if 'dof' not in cons:
                errors.append(f"Constraint {i}: missing 'dof'")
                continue
            
            node_id = cons['node_id']
            dof = cons['dof']
            
            # 检查节点 ID 范围
            if node_id < 1 or node_id > num_nodes:
                errors.append(
                    f"Constraint {i}: node_id {node_id} out of range [1, {num_nodes}]"
                )
                continue
            
            # 检查 DOF 范围
            if dof < 0 or dof > 2:
                errors.append(
                    f"Constraint {i}: dof {dof} out of range [0, 2] (0=x, 1=y, 2=z)"
                )
                continue
            
            valid_constraints.append(cons)
        
        return valid_constraints, errors
