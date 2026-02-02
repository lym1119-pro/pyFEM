# 文件: PyMFEA/core/materials/__init__.py
"""
PyMFEA 材料系统

分层架构:
- interfaces.py: 抽象基类和协议
- state.py: 材料状态管理
- elastic/: 弹性模型组件
- plastic/: 塑性模型组件 (屈服函数、硬化规律、返回映射)
- models/: 预置材料模型
- factory.py: 材料工厂

使用方法:
    from core.materials import MaterialFactory, PlasticState
    
    # 创建材料
    mat = MaterialFactory.create_j2_plastic(
        E=210e9, nu=0.3, yield_stress=250e6, hardening=1e9
    )
    
    # 创建状态
    state = mat.create_state()
    
    # 计算应力
    result = mat.compute_stress(F, state, dt=1.0)
    print(result.stress)       # 应力 Voigt 向量
    print(result.tangent)      # 切线模量
    print(result.is_plastic)   # 是否塑性
    
扩展指南:
    添加新屈服准则:
        1. 在 plastic/yield_functions.py 添加新类
        2. 实现 evaluate() 和 gradient() 方法
        
    添加新硬化模型:
        1. 在 plastic/hardening.py 添加新类
        2. 实现 get_yield_stress() 和 get_hardening_modulus() 方法
        
    添加新材料模型:
        1. 在 models/ 目录添加新文件
        2. 继承 Material 基类，实现 compute_stress() 和 create_state()
"""

# 核心接口
from .interfaces import (
    Material,
    StressResult,
    ElasticModel,
    YieldFunction,
    HardeningLaw,
    tensor_to_voigt,
    voigt_to_tensor,
    stress_to_tensor,
    tensor_to_stress,
)

# 状态管理
from .state import PlasticState

# 工厂
from .factory import MaterialFactory

# 弹性组件
from .elastic import IsotropicElastic

# 塑性组件
from .plastic import (
    VonMises,
    DruckerPrager,
    PerfectPlasticity,
    LinearIsotropicHardening,
    KinematicHardening,
    RadialReturn,
)

# 预置模型
from .models import J2PlasticMaterial


__all__ = [
    # 核心接口
    'Material',
    'StressResult',
    'ElasticModel',
    'YieldFunction',
    'HardeningLaw',
    
    # 辅助函数
    'tensor_to_voigt',
    'voigt_to_tensor',
    'stress_to_tensor',
    'tensor_to_stress',
    
    # 状态
    'PlasticState',
    
    # 工厂
    'MaterialFactory',
    
    # 弹性组件
    'IsotropicElastic',
    
    # 塑性组件
    'VonMises',
    'DruckerPrager',
    'PerfectPlasticity',
    'LinearIsotropicHardening',
    'KinematicHardening',
    'RadialReturn',
    
    # 预置模型
    'J2PlasticMaterial',
]
