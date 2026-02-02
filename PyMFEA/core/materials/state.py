# 文件: PyMFEA/core/materials/state.py
"""
材料状态管理

PlasticState: 塑性材料的状态容器，存储积分点的历史变量
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class PlasticState:
    """
    塑性材料状态容器
    
    存储积分点的历史变量，用于增量塑性计算。
    
    Attributes:
        stress: 应力 Voigt 向量 [σxx, σyy, σzz, σyz, σxz, σxy]
        equivalent_plastic_strain: 累积等效塑性应变 ε̄ᵖ
        plastic_strain: 塑性应变 Voigt 向量
        back_stress: 背应力 (随动硬化使用)
    
    Example:
        state = PlasticState()
        # ... 材料计算 ...
        committed_state = state.copy()  # 收敛后保存
    """
    
    # 应力状态 (Voigt 向量)
    stress: np.ndarray = field(default_factory=lambda: np.zeros(6))
    
    # 标量内变量
    equivalent_plastic_strain: float = 0.0
    
    # 张量内变量
    plastic_strain: np.ndarray = field(default_factory=lambda: np.zeros(6))
    back_stress: np.ndarray = field(default_factory=lambda: np.zeros(6))
    
    def copy(self) -> 'PlasticState':
        """
        深拷贝
        
        用于在时间步收敛后保存 committed 状态。
        
        Returns:
            PlasticState: 独立的状态副本
        """
        return PlasticState(
            stress=self.stress.copy(),
            equivalent_plastic_strain=self.equivalent_plastic_strain,
            plastic_strain=self.plastic_strain.copy(),
            back_stress=self.back_stress.copy()
        )
    
    def clone(self) -> 'PlasticState':
        """深拷贝 (copy 的别名)"""
        return self.copy()
    
    def reset(self) -> None:
        """重置为初始状态"""
        self.stress = np.zeros(6)
        self.equivalent_plastic_strain = 0.0
        self.plastic_strain = np.zeros(6)
        self.back_stress = np.zeros(6)
    
    def __repr__(self) -> str:
        return (
            f"PlasticState(ep={self.equivalent_plastic_strain:.6f}, "
            f"stress_max={np.max(np.abs(self.stress)):.2e})"
        )
