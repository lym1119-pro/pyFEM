# 文件: PyMFEA/core/materials/plastic/yield_functions.py
"""
屈服函数模块

提供各种屈服准则:
- VonMises: Von Mises (J2) 屈服准则
- DruckerPrager: Drucker-Prager 屈服准则 (骨架)

扩展指南:
    要添加新的屈服函数，只需创建一个类实现以下方法:
    - evaluate(stress, yield_stress) -> float
    - gradient(stress) -> np.ndarray (6,)
"""

import numpy as np


class VonMises:
    """
    Von Mises (J2) 屈服准则
    
    屈服函数: f = σ_eq - σ_y
    其中 σ_eq = √(3/2 * s:s) = √(3 * J2)
    
    适用于金属材料的等向屈服。
    
    Example:
        yield_fn = VonMises()
        f = yield_fn.evaluate(stress, yield_stress=250e6)
        if f > 0:
            n = yield_fn.gradient(stress)  # 流动方向
    """
    
    def evaluate(self, stress: np.ndarray, yield_stress: float) -> float:
        """
        计算屈服函数值
        
        Args:
            stress: 应力 Voigt 向量 (6,) [σxx, σyy, σzz, σyz, σxz, σxy]
            yield_stress: 当前屈服应力 σ_y
            
        Returns:
            f: 屈服函数值
               f <= 0: 弹性状态
               f > 0: 需要塑性修正
        """
        sigma_eq = self._equivalent_stress(stress)
        return sigma_eq - yield_stress
    
    def gradient(self, stress: np.ndarray) -> np.ndarray:
        """
        计算屈服函数对应力的梯度 (流动方向)
        
        对于 Von Mises: n = ∂f/∂σ = (3/2) * s / σ_eq
        
        Args:
            stress: 应力 Voigt 向量 (6,)
            
        Returns:
            n: 归一化流动方向 (6,)
        """
        s = self._deviatoric(stress)
        sigma_eq = self._equivalent_stress(stress)
        
        if sigma_eq < 1e-10:
            return np.zeros(6)
        
        # n = (3/2) * s / σ_eq
        # 注意 Voigt 约定：剪切分量需要考虑因子
        n = np.zeros(6)
        n[0] = 1.5 * s[0] / sigma_eq
        n[1] = 1.5 * s[1] / sigma_eq
        n[2] = 1.5 * s[2] / sigma_eq
        # 剪切分量：Voigt 中 σxy 对应真实应力，但梯度中需要因子
        n[3] = 3.0 * s[3] / sigma_eq  # σyz
        n[4] = 3.0 * s[4] / sigma_eq  # σxz
        n[5] = 3.0 * s[5] / sigma_eq  # σxy
        
        return n
    
    def equivalent_stress(self, stress: np.ndarray) -> float:
        """
        计算 Von Mises 等效应力 (公开接口)
        
        σ_eq = √(3/2 * s:s)
        """
        return self._equivalent_stress(stress)
    
    def _equivalent_stress(self, stress: np.ndarray) -> float:
        """
        计算 Von Mises 等效应力
        
        σ_eq = √(σ_xx² + σ_yy² + σ_zz² - σ_xx*σ_yy - σ_yy*σ_zz - σ_zz*σ_xx 
               + 3*(σ_xy² + σ_yz² + σ_xz²))
        
        等价于: σ_eq = √(3/2 * s:s) = √(3 * J2)
        """
        s = self._deviatoric(stress)
        # s:s = s[0]² + s[1]² + s[2]² + 2*(s[3]² + s[4]² + s[5]²)
        # 注意剪切分量在 Voigt 中存储的是 σyz, σxz, σxy (非工程应变)
        return np.sqrt(1.5 * (s[0]**2 + s[1]**2 + s[2]**2 + 
                              2 * (s[3]**2 + s[4]**2 + s[5]**2)))
    
    def _deviatoric(self, stress: np.ndarray) -> np.ndarray:
        """
        计算偏应力
        
        s = σ - (1/3) * tr(σ) * I
        """
        p = (stress[0] + stress[1] + stress[2]) / 3.0
        s = stress.copy()
        s[0] -= p
        s[1] -= p
        s[2] -= p
        return s
    
    def __repr__(self) -> str:
        return "VonMises()"


class DruckerPrager:
    """
    Drucker-Prager 屈服准则 (骨架实现)
    
    屈服函数: f = √J2 + α * I1 - k
    
    适用于岩土材料，考虑围压效应。
    
    注意: 这是一个骨架实现，完整功能待后续开发。
    """
    
    def __init__(self, alpha: float, k: float):
        """
        Args:
            alpha: 材料参数，控制围压敏感性
            k: 材料参数，与内聚力相关
        """
        self.alpha = alpha
        self.k = k
    
    def evaluate(self, stress: np.ndarray, yield_stress: float) -> float:
        """计算屈服函数值"""
        raise NotImplementedError(
            "DruckerPrager is a skeleton implementation. "
            "Full implementation to be added in future versions."
        )
    
    def gradient(self, stress: np.ndarray) -> np.ndarray:
        """计算屈服函数梯度"""
        raise NotImplementedError(
            "DruckerPrager is a skeleton implementation. "
            "Full implementation to be added in future versions."
        )
    
    def __repr__(self) -> str:
        return f"DruckerPrager(alpha={self.alpha}, k={self.k})"
