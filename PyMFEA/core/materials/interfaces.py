# 文件: PyMFEA/core/materials/interfaces.py
"""
材料系统核心接口定义

设计原则:
1. Material: 所有材料的抽象基类，定义统一的 compute_stress 接口
2. StressResult: 标准化的应力计算返回值
3. Protocol: 组件接口，使用鸭子类型实现松耦合
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Literal, Protocol, Tuple, runtime_checkable
import numpy as np


@dataclass
class StressResult:
    """
    统一的应力计算结果
    
    Attributes:
        stress: 应力 Voigt 向量 (6,) [σxx, σyy, σzz, σyz, σxz, σxy]
        tangent: 切线模量 (6,6)
        state: 更新后的材料状态 (用于塑性历史跟踪)
        is_plastic: 是否发生塑性变形
        stress_type: 应力类型 ('cauchy', 'pk2', 'kirchhoff')
    """
    stress: np.ndarray
    tangent: np.ndarray
    state: Optional[object] = None
    is_plastic: bool = False
    stress_type: Literal['cauchy', 'pk2', 'kirchhoff'] = 'cauchy'


class Material(ABC):
    """
    材料抽象基类
    
    所有材料都必须实现:
    - compute_stress(): 核心应力计算方法
    - create_state(): 创建材料状态 (弹性材料返回 None)
    - stress_type: 返回的应力类型
    
    Example:
        mat = J2PlasticMaterial(E=210e9, nu=0.3, yield_stress=250e6)
        state = mat.create_state()
        result = mat.compute_stress(F, state, dt=1.0)
    """
    
    @abstractmethod
    def compute_stress(
        self, 
        F: np.ndarray, 
        state: Optional[object] = None, 
        dt: float = 1.0
    ) -> StressResult:
        """
        从变形梯度计算应力
        
        Args:
            F: 变形梯度张量 (3,3)
            state: 材料状态对象 (用于历史相关材料)
            dt: 时间增量 (用于率相关材料)
            
        Returns:
            StressResult: 包含应力、切线模量和更新后的状态
        """
        pass
    
    @abstractmethod
    def create_state(self) -> Optional[object]:
        """
        创建初始材料状态
        
        Returns:
            对于弹性材料返回 None
            对于塑性材料返回 PlasticState 实例
        """
        pass
    
    @property
    @abstractmethod
    def stress_type(self) -> Literal['cauchy', 'pk2', 'kirchhoff']:
        """
        返回应力类型
        
        - 'pk2': 第二类 Piola-Kirchhoff 应力 (TL 格式)
        - 'cauchy': 柯西应力 (UL 格式)
        - 'kirchhoff': Kirchhoff 应力 τ = J * σ
        """
        pass


# =============================================================================
# 组件协议 (Protocol for duck typing)
# 使用 Protocol 而非 ABC，允许更灵活的组合
# =============================================================================

@runtime_checkable
class ElasticModel(Protocol):
    """
    弹性模型协议
    
    任何实现了以下方法的类都可以作为弹性模型使用:
    - compute_stress(): 计算弹性应力
    - mu: 剪切模量
    - K: 体积模量
    - D: 弹性矩阵
    """
    
    @property
    def mu(self) -> float:
        """剪切模量 G"""
        ...
    
    @property
    def K(self) -> float:
        """体积模量 K"""
        ...
    
    @property
    def D(self) -> np.ndarray:
        """弹性矩阵 (6,6)"""
        ...
    
    def compute_stress(self, strain_voigt: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算弹性应力
        
        Args:
            strain_voigt: 应变 Voigt 向量 (6,)
            
        Returns:
            (stress, tangent): 应力向量和切线模量
        """
        ...


@runtime_checkable
class YieldFunction(Protocol):
    """
    屈服函数协议
    
    任何实现了以下方法的类都可以作为屈服函数使用:
    - evaluate(): 计算屈服函数值
    - gradient(): 计算屈服函数梯度 (流动方向)
    """
    
    def evaluate(self, stress: np.ndarray, yield_stress: float) -> float:
        """
        计算屈服函数值
        
        Args:
            stress: 应力 Voigt 向量 (6,)
            yield_stress: 当前屈服应力
            
        Returns:
            f: 屈服函数值 (f <= 0 表示弹性，f > 0 表示需要返回)
        """
        ...
    
    def gradient(self, stress: np.ndarray) -> np.ndarray:
        """
        计算屈服函数对应力的梯度
        
        Args:
            stress: 应力 Voigt 向量 (6,)
            
        Returns:
            n: 流动方向向量 (6,)
        """
        ...


@runtime_checkable
class HardeningLaw(Protocol):
    """
    硬化律协议
    
    任何实现了以下方法的类都可以作为硬化律使用:
    - get_yield_stress(): 获取当前屈服应力
    - get_hardening_modulus(): 获取硬化模量
    """
    
    def get_yield_stress(self, ep: float) -> float:
        """
        获取当前屈服应力
        
        Args:
            ep: 累积等效塑性应变
            
        Returns:
            σ_y: 当前屈服应力
        """
        ...
    
    def get_hardening_modulus(self, ep: float) -> float:
        """
        获取硬化模量
        
        Args:
            ep: 累积等效塑性应变
            
        Returns:
            H: 硬化模量 dσ_y/dε_p
        """
        ...


# =============================================================================
# 辅助函数
# =============================================================================

def tensor_to_voigt(T: np.ndarray, engineering: bool = True) -> np.ndarray:
    """
    将 3x3 对称张量转换为 Voigt 向量
    
    Args:
        T: 对称张量 (3,3)
        engineering: True 返回工程形式 [T11,T22,T33,2T23,2T13,2T12]
                    False 返回张量形式 [T11,T22,T33,T23,T13,T12]
    """
    factor = 2.0 if engineering else 1.0
    return np.array([
        T[0, 0], T[1, 1], T[2, 2],
        factor * T[1, 2], factor * T[0, 2], factor * T[0, 1]
    ])


def voigt_to_tensor(v: np.ndarray, engineering: bool = True) -> np.ndarray:
    """
    将 Voigt 向量转换为 3x3 对称张量
    
    Args:
        v: Voigt 向量 (6,)
        engineering: True 输入为工程形式，False 输入为张量形式
    """
    factor = 0.5 if engineering else 1.0
    return np.array([
        [v[0], factor * v[5], factor * v[4]],
        [factor * v[5], v[1], factor * v[3]],
        [factor * v[4], factor * v[3], v[2]]
    ])


def stress_to_tensor(s: np.ndarray) -> np.ndarray:
    """将应力 Voigt 向量转换为 3x3 张量 (应力不需要因子)"""
    return np.array([
        [s[0], s[5], s[4]],
        [s[5], s[1], s[3]],
        [s[4], s[3], s[2]]
    ])


def tensor_to_stress(T: np.ndarray) -> np.ndarray:
    """将 3x3 应力张量转换为 Voigt 向量"""
    return np.array([
        T[0, 0], T[1, 1], T[2, 2],
        T[1, 2], T[0, 2], T[0, 1]
    ])
