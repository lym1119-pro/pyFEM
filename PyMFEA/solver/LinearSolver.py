import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import cg, spsolve

class LinearSolver:
    """
    线性方程组求解器
    对应 PDF: SolveS3d8n.m
    包含：
    1. 罚函数法引入边界条件 (Penalty Method)
    2. 共轭梯度法求解 (PCG)
    """
    
    def __init__(self, K_global, F_global):
        """
        Args:
            K_global: 全局刚度矩阵 (scipy.sparse matrix)
            F_global: 全局载荷向量 (numpy array)
        """
        self.K = K_global
        self.F = F_global
        
        # 罚因子倍数，对应 PDF 1.7.1 节建议的 10^4 ~ 10^9
        # PDF 代码中使用 1e9 [cite: 1312]
        self.penalty_multiplier = 1e9

    def apply_boundary_conditions(self, constraints):
        """
        使用罚函数法修改 K 和 F
        现在使用统一的 BoundaryConditionHandler
        
        Args:
            constraints (list of dict): 约束列表
                格式: {'node_id': 1, 'dof': 0, 'value': 0.0} 
                (注意：dof 0=x, 1=y, 2=z)
        """
        from solver.boundary_conditions import BoundaryConditionHandler
        
        print(f"应用罚函数法... (Multiplier = {self.penalty_multiplier:.2e})")
        
        return BoundaryConditionHandler.apply_penalty_method(
            self.K,
            self.F,
            constraints,
            penalty_multiplier=self.penalty_multiplier,
            is_sparse=True
        )

    def solve(self, constraints, method='cg', tol=1e-6, max_iter=5000):
        """
        执行求解
        对应 PDF: SolveS3d8n.m lines 20-22 [cite: 1339-1341]
        """
        # 1. 应用边界条件
        K_final, F_final = self.apply_boundary_conditions(constraints)
        
        print(f"开始求解线性方程组 (Method: {method})...")
        
        # 2. 求解 Ax = b
        if method == 'cg':
            # 共轭梯度法 (Conjugate Gradient)
            # 对应 PDF 1.7.2 节 [cite: 169-180]
            # SciPy 的 cg 比 PDF 手写的 conjugate_gradient.m 更健壮
            u, info = cg(K_final, F_final, rtol=tol, maxiter=max_iter)
            
            if info > 0:
                print(f"Warning: CG 求解器未达到收敛容差 (Exit code {info})")
            elif info < 0:
                print("Error: CG 求解器输入非法")
            else:
                print("CG 求解收敛。")
                
        elif method == 'direct':
            # 直接法 (Direct Solver)，作为备用选项
            # 适合中小规模问题，比 CG 更稳定
            u = spsolve(K_final, F_final)
            print("直接法求解完成。")
            
        else:
            raise ValueError(f"Unknown solver method: {method}")
            
        return u

