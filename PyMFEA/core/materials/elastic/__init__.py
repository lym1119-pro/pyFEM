# 文件: PyMFEA/core/materials/elastic/__init__.py
"""
弹性模型模块

提供各种弹性响应模型:
- IsotropicElastic: 各向同性线弹性
- (未来可扩展: OrthotropicElastic, NeoHookean, etc.)
"""

from .isotropic import IsotropicElastic

__all__ = ['IsotropicElastic']
