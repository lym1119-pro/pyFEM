# 文件: PyMFEA/core/materials/plastic/hardening.py
"""
硬化规律模块

提供各种硬化模型:
- PerfectPlasticity: 理想塑性 (无硬化)
- LinearIsotropicHardening: 线性等向硬化
- KinematicHardening: 线性随动硬化 (骨架)

扩展指南:
    要添加新的硬化模型，只需创建一个类实现以下方法:
    - get_yield_stress(ep) -> float
    - get_hardening_modulus(ep) -> float
"""

import numpy as np


class PerfectPlasticity:
    """
    理想塑性 (无硬化)
    
    屈服应力保持恒定: σ_y = σ_y0
    
    适用于软化分析之前的简化模型。
    
    Example:
        hardening = PerfectPlasticity(yield_stress=250e6)
        sigma_y = hardening.get_yield_stress(ep=0.05)  # 始终返回 250e6
    """
    
    def __init__(self, yield_stress: float):
        """
        Args:
            yield_stress: 屈服应力 σ_y0
        """
        if yield_stress <= 0:
            raise ValueError(f"Yield stress must be positive, got {yield_stress}")
        self.yield_stress = float(yield_stress)
    
    def get_yield_stress(self, ep: float) -> float:
        """
        获取当前屈服应力
        
        Args:
            ep: 累积等效塑性应变 (不使用)
            
        Returns:
            σ_y: 屈服应力 (恒定)
        """
        return self.yield_stress
    
    def get_hardening_modulus(self, ep: float) -> float:
        """
        获取硬化模量
        
        Args:
            ep: 累积等效塑性应变 (不使用)
            
        Returns:
            H: 硬化模量 = 0
        """
        return 0.0
    
    def __repr__(self) -> str:
        return f"PerfectPlasticity(σ_y={self.yield_stress:.2e})"


class LinearIsotropicHardening:
    """
    线性等向硬化
    
    屈服应力随等效塑性应变线性增加:
    σ_y = σ_y0 + H * ε_p
    
    适用于大多数金属材料的简化模型。
    
    Example:
        hardening = LinearIsotropicHardening(yield_stress=250e6, H=1e9)
        sigma_y = hardening.get_yield_stress(ep=0.05)  # 返回 300e6
    """
    
    def __init__(self, yield_stress: float, H: float):
        """
        Args:
            yield_stress: 初始屈服应力 σ_y0
            H: 硬化模量 (塑性模量)
        """
        if yield_stress <= 0:
            raise ValueError(f"Yield stress must be positive, got {yield_stress}")
        if H < 0:
            raise ValueError(f"Hardening modulus must be non-negative, got {H}")
        
        self.yield_stress = float(yield_stress)
        self.H = float(H)
    
    def get_yield_stress(self, ep: float) -> float:
        """
        获取当前屈服应力
        
        Args:
            ep: 累积等效塑性应变
            
        Returns:
            σ_y: 当前屈服应力 = σ_y0 + H * ε_p
        """
        return self.yield_stress + self.H * ep
    
    def get_hardening_modulus(self, ep: float) -> float:
        """
        获取硬化模量
        
        Args:
            ep: 累积等效塑性应变 (线性硬化不使用)
            
        Returns:
            H: 硬化模量 (恒定)
        """
        return self.H
    
    def __repr__(self) -> str:
        return f"LinearIsotropicHardening(σ_y={self.yield_stress:.2e}, H={self.H:.2e})"


class KinematicHardening:
    """
    线性随动硬化 (骨架实现)
    
    使用 Prager 规则：背应力演化与塑性应变率成正比
    α̇ = (2/3) * C * ε̇_p
    
    适用于循环加载分析。
    
    注意: 这是一个骨架实现，完整功能待后续开发。
    """
    
    def __init__(self, yield_stress: float, C: float):
        """
        Args:
            yield_stress: 初始屈服应力
            C: 随动硬化模量
        """
        self.yield_stress = float(yield_stress)
        self.C = float(C)
    
    def get_yield_stress(self, ep: float) -> float:
        """
        获取屈服应力
        
        纯随动硬化下屈服面半径不变
        """
        return self.yield_stress
    
    def get_hardening_modulus(self, ep: float) -> float:
        """
        获取等效硬化模量
        
        对于随动硬化，这里返回 C 用于一致切线计算
        """
        return self.C
    
    def update_back_stress(
        self, 
        back_stress_old: np.ndarray, 
        d_gamma: float, 
        n: np.ndarray
    ) -> np.ndarray:
        """
        更新背应力
        
        α_new = α_old + (2/3) * C * Δγ * n
        
        Args:
            back_stress_old: 旧背应力 (6,)
            d_gamma: 塑性乘子增量
            n: 流动方向 (6,)
            
        Returns:
            back_stress_new: 更新后的背应力 (6,)
        """
        return back_stress_old + (2.0 / 3.0) * self.C * d_gamma * n
    
    def __repr__(self) -> str:
        return f"KinematicHardening(σ_y={self.yield_stress:.2e}, C={self.C:.2e})"
