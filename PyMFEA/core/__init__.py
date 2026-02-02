# 文件: PyMFEA/core/__init__.py
"""
PyMFEA 核心模块

导出材料、单元、状态管理等核心类
"""

# ==============================================================================
# 材料系统 (新架构)
# ==============================================================================
from core.materials import (
    # 核心接口
    Material,
    StressResult,
    
    # 状态
    PlasticState,
    
    # 工厂
    MaterialFactory,
    
    # 弹性组件
    IsotropicElastic,
    
    # 塑性组件
    VonMises,
    PerfectPlasticity,
    LinearIsotropicHardening,
    RadialReturn,
    
    # 预置模型
    J2PlasticMaterial,
    
    # 辅助函数
    tensor_to_voigt,
    voigt_to_tensor,
)

# ==============================================================================
# 单元
# ==============================================================================
from core.element_nonlinear import C3D8_Nonlinear_Base, C3D8_TL, C3D8_UL
from core.element import C3D8Element

# ==============================================================================
# 其他
# ==============================================================================
from core.node import Node
from core.quadrature import Quadrature


__all__ = [
    # === 材料系统 ===
    'Material',
    'StressResult',
    'PlasticState',
    'MaterialFactory',
    'J2PlasticMaterial',
    'IsotropicElastic',
    'VonMises',
    'PerfectPlasticity',
    'LinearIsotropicHardening',
    'RadialReturn',
    'tensor_to_voigt',
    'voigt_to_tensor',
    
    # === 单元 ===
    'C3D8_Nonlinear_Base',
    'C3D8_TL',
    'C3D8_UL',
    'C3D8Element',
    
    # === 其他 ===
    'Node',
    'Quadrature',
]
