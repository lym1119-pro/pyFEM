# 文件: PyMFEA/core/materials/plastic/return_mapping.py
"""
返回映射算法模块

提供塑性修正算法:
- RadialReturn: 径向返回算法 (适用于 J2 塑性)

扩展指南:
    要添加新的返回映射算法 (如 CPP)，只需创建一个类实现:
    - apply(stress_trial, ep_old) -> (stress, tangent, ep_new, is_plastic)
"""

import numpy as np
from typing import Tuple


class RadialReturn:
    """
    径向返回算法 (Radial Return Algorithm)
    
    适用于 J2 (Von Mises) 塑性的经典返回映射算法。
    由于 J2 屈服面是球形，返回路径为径向（直线），故名径向返回。
    
    算法步骤:
    1. 计算弹性试探应力
    2. 检查屈服条件 f = σ_eq - σ_y
    3. 若 f > 0，计算塑性乘子 Δγ = f / (3μ + H)
    4. 修正应力: σ = σ_trial - 2μ * Δγ * n
    5. 更新状态变量: ε_p_new = ε_p_old + Δγ
    
    Attributes:
        elastic: 弹性模型 (需提供 mu, D)
        yield_fn: 屈服函数 (需提供 evaluate, gradient)
        hardening: 硬化规律 (需提供 get_yield_stress, get_hardening_modulus)
    
    Example:
        return_mapping = RadialReturn(elastic, yield_fn, hardening)
        stress, tangent, ep_new, is_plastic = return_mapping.apply(
            stress_trial, ep_old
        )
    """
    
    def __init__(self, elastic, yield_fn, hardening):
        """
        Args:
            elastic: 弹性模型对象
            yield_fn: 屈服函数对象
            hardening: 硬化规律对象
        """
        self.elastic = elastic
        self.yield_fn = yield_fn
        self.hardening = hardening
    
    def apply(
        self, 
        stress_trial: np.ndarray, 
        ep_old: float
    ) -> Tuple[np.ndarray, np.ndarray, float, bool]:
        """
        执行返回映射
        
        Args:
            stress_trial: 弹性试探应力 (6,)
            ep_old: 当前等效塑性应变
            
        Returns:
            stress: 修正后的应力 (6,)
            tangent: 一致切线模量 (6,6)
            ep_new: 更新后的等效塑性应变
            is_plastic: 是否发生塑性流动
        """
        # 获取当前屈服应力
        sigma_y = self.hardening.get_yield_stress(ep_old)
        
        # 检查屈服条件
        f_trial = self.yield_fn.evaluate(stress_trial, sigma_y)
        
        if f_trial <= 0:
            # 弹性状态：无需修正
            return stress_trial.copy(), self.elastic.D.copy(), ep_old, False
        
        # 塑性修正
        mu = self.elastic.mu
        H = self.hardening.get_hardening_modulus(ep_old)
        
        # 计算塑性乘子
        # Δγ = f_trial / (3μ + H)
        d_gamma = f_trial / (3.0 * mu + H)
        
        # 流动方向
        n = self.yield_fn.gradient(stress_trial)
        
        # 应力修正: σ = σ_trial - 2μ * Δγ * n
        # 注意：对于 J2 塑性，只修正偏应力部分
        stress = stress_trial - 2.0 * mu * d_gamma * n
        
        # 更新等效塑性应变
        ep_new = ep_old + d_gamma
        
        # 计算算法一致切线模量
        tangent = self._compute_consistent_tangent(n, d_gamma, stress_trial, ep_old)
        
        return stress, tangent, ep_new, True
    
    def _compute_consistent_tangent(
        self, 
        n: np.ndarray, 
        d_gamma: float,
        stress_trial: np.ndarray,
        ep: float
    ) -> np.ndarray:
        """
        计算算法一致切线模量 (精确版)
        
        D^{alg} = D^e - c1 * I_dev - (c2 - 2/3 * c1) * (n ⊗ n)
        
        其中:
        c1 = 6μ² Δγ / σ_eq_trial  (径向回缩导致的刚度降低)
        c2 = 4μ² / (3μ + H)       (塑性流动导致的刚度降低)
        
        此公式提供了二次收敛所需的精确 Jacobian。
        """
        D = self.elastic.D.copy()
        mu = self.elastic.mu
        H = self.hardening.get_hardening_modulus(ep)
        
        # 计算等效试探应力
        sigma_eq_trial = self.yield_fn.equivalent_stress(stress_trial)
        if sigma_eq_trial < 1e-10:
            return D

        # 系数 c1, c2
        # c1: 几何修正 (由于径向返回)
        c1 = 6.0 * mu * mu * d_gamma / sigma_eq_trial
        
        # c2: 连续体弹塑性修正
        c2 = 4.0 * mu * mu / (3.0 * mu + H)
        
        # 组合系数对于 n ⊗ n
        beta_n = c2 - c1 * (2.0 / 3.0)
        
        n_outer = np.outer(n, n)
        
        # 偏应力投影张量 (Voigt 6x6)
        # I_dev @ v = v_dev
        I_dev = np.array([
            [ 2/3, -1/3, -1/3, 0, 0, 0],
            [-1/3,  2/3, -1/3, 0, 0, 0],
            [-1/3, -1/3,  2/3, 0, 0, 0],
            [   0,    0,    0, 1, 0, 0],
            [   0,    0,    0, 0, 1, 0],
            [   0,    0,    0, 0, 0, 1]
        ], dtype=float)
        
        # 组装 D_alg
        # 注意：剪切部分在 Voigt 下，I_dev 对角线是 1
        # 但 D 矩阵中剪切部分是 mu (不是 2mu)，所以直接减 c1 也是对的
        # 因为 D^e_dev = 2mu * I_dev_tensor
        # D_alg_dev = (2mu - c1) * I_dev_tensor
        # 在 Voigt 中，D^e 剪切项就是 mu
        # c1 来源于 2mu * factor，所以剪切项减去 c1/2 ?
        # 等等，如果 dE 只有 shear (gamma)
        # dS = mu * gamma
        # I_dev @ [0...gamma] = [0...gamma]
        # c1 * I_dev contribution is c1 * gamma
        # So effective G = mu - c1
        # D_alg formula says 2mu_eff = 2mu - c1
        # So G_eff = mu - 0.5 * c1
        
        # 必须小心 Voigt 的剪切项！
        # I_dev 矩阵是针对 "Tensor components" 还是 "Engineering components"?
        # I_dev @ [e1, e2, e3, gam23, ...] 
        # result should be [e1_dev, ..., gam23]
        # Yes, I_dev diagonal is 1 for shear.
        # So (c1 * I_dev) @ E gives term with c1.
        # But we want 2mu reduction to match 2mu - c1
        # In Voigt shear row: sigma = mu * gamma.
        # New sigma = (mu - 0.5 c1) * gamma.
        # So we should subtract 0.5 * c1 from shear rows.
        
        # 为了避免这种混淆，我们直接修改 I_dev 的剪切项系数
        I_dev_mod = I_dev.copy()
        I_dev_mod[3,3] = 0.5
        I_dev_mod[4,4] = 0.5
        I_dev_mod[5,5] = 0.5
        
        D_tang = D - c1 * I_dev_mod - beta_n * n_outer
        
        return D_tang
    
    def __repr__(self) -> str:
        return f"RadialReturn(elastic={self.elastic}, yield_fn={self.yield_fn}, hardening={self.hardening})"
