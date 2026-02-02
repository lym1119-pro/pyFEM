# 文件: PyMFEA/core/materials/models/__init__.py
"""
预置材料模型

提供组装好的、可直接使用的材料模型:
- J2PlasticMaterial: J2 弹塑性材料
"""

from .j2_plasticity import J2PlasticMaterial

__all__ = ['J2PlasticMaterial']
