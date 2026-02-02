# 文件: PyMFEA/core/materials/models/j2_plasticity.py
"""
J2 弹塑性材料模型

使用组合模式将弹性模型、屈服函数、硬化规律和返回映射算法组合成完整的材料。
"""

import numpy as np
from typing import Optional

from ..interfaces import Material, StressResult, tensor_to_voigt
from ..state import PlasticState
from ..elastic.isotropic import IsotropicElastic
from ..plastic.yield_functions import VonMises
from ..plastic.hardening import PerfectPlasticity, LinearIsotropicHardening
from ..plastic.return_mapping import RadialReturn


class J2PlasticMaterial(Material):
    """
    J2 弹塑性材料 (组合式实现)
    
    将各组件组合成完整的材料模型:
    - 弹性: IsotropicElastic
    - 屈服: VonMises
    - 硬化: PerfectPlasticity 或 LinearIsotropicHardening
    - 返回映射: RadialReturn
    
    支持:
    - 理想塑性 (hardening=0)
    - 线性等向硬化 (hardening>0)
    - TL 格式 (返回 PK2 应力)
    
    Attributes:
        E: 杨氏模量
        nu: 泊松比
        yield_stress: 初始屈服应力
        hardening: 硬化模量 (0 表示理想塑性)
    
    Example:
        # 理想弹塑性
        mat = J2PlasticMaterial(E=210e9, nu=0.3, yield_stress=250e6)
        
        # 线性硬化
        mat = J2PlasticMaterial(E=210e9, nu=0.3, yield_stress=250e6, hardening=1e9)
        
        # 使用
        state = mat.create_state()
        result = mat.compute_stress(F, state, dt=1.0)
    """
    
    def __init__(
        self, 
        E: float, 
        nu: float, 
        yield_stress: float, 
        hardening: float = 0.0
    ):
        """
        初始化 J2 弹塑性材料
        
        Args:
            E: 杨氏模量
            nu: 泊松比
            yield_stress: 初始屈服应力 σ_y0
            hardening: 线性硬化模量 H (0 表示理想塑性)
        """
        # 保存参数
        self.E = float(E)
        self.nu = float(nu)
        self.yield_stress = float(yield_stress)
        self.hardening_modulus = float(hardening)
        
        # 创建组件
        self.elastic = IsotropicElastic(E, nu)
        self.yield_fn = VonMises()
        
        if hardening == 0:
            self.hardening = PerfectPlasticity(yield_stress)
        else:
            self.hardening = LinearIsotropicHardening(yield_stress, hardening)
        
        self.return_mapping = RadialReturn(self.elastic, self.yield_fn, self.hardening)
        
        # 应力类型 (TL 格式使用 PK2)
        self._stress_type = 'pk2'
    
    @property
    def stress_type(self):
        """返回应力类型"""
        return self._stress_type
    
    @property
    def mu(self) -> float:
        """剪切模量"""
        return self.elastic.mu
    
    @property
    def K(self) -> float:
        """体积模量"""
        return self.elastic.K
    
    @property
    def D(self) -> np.ndarray:
        """弹性矩阵"""
        return self.elastic.D
    
    @property
    def D_matrix(self) -> np.ndarray:
        """弹性矩阵 (兼容线性单元)"""
        return self.elastic.D
    
    def create_state(self) -> PlasticState:
        """创建初始材料状态"""
        return PlasticState()
    
    def compute_stress(
        self, 
        F: np.ndarray, 
        state: Optional[PlasticState] = None, 
        dt: float = 1.0
    ) -> StressResult:
        """
        从变形梯度计算应力
        
        算法流程:
        1. 计算 Green-Lagrange 应变 E = 0.5(F^T F - I)
        2. 计算弹性试探应力 S_trial = D : E
        3. 执行返回映射 (若需要)
        4. 返回 PK2 应力和一致切线模量
        
        Args:
            F: 变形梯度张量 (3,3)
            state: 材料状态 (若为 None，将创建新状态)
            dt: 时间增量 (当前版本不使用)
            
        Returns:
            StressResult: 包含应力、切线模量和更新后的状态
        """
        if state is None:
            state = self.create_state()
        
        # 1. 计算 Green-Lagrange 应变
        C = F.T @ F  # 右 Cauchy-Green 张量
        E_tensor = 0.5 * (C - np.eye(3))
        E_voigt = tensor_to_voigt(E_tensor, engineering=True)
        
        # 2. 弹性试探应力
        stress_trial, _ = self.elastic.compute_stress(E_voigt)
        
        # 3. 返回映射
        stress, tangent, ep_new, is_plastic = self.return_mapping.apply(
            stress_trial, 
            state.equivalent_plastic_strain
        )
        
        # 4. 更新状态 (创建新状态，不修改输入)
        new_state = state.copy()
        new_state.stress = stress.copy()
        new_state.equivalent_plastic_strain = ep_new
        
        return StressResult(
            stress=stress,
            tangent=tangent,
            state=new_state,
            is_plastic=is_plastic,
            stress_type=self._stress_type
        )
    
    def __repr__(self) -> str:
        return (
            f"J2PlasticMaterial(E={self.E:.2e}, nu={self.nu:.3f}, "
            f"σ_y={self.yield_stress:.2e}, H={self.hardening_modulus:.2e})"
        )
