# 文件: PyMFEA/core/materials/elastic/isotropic.py
"""
各向同性弹性模型

提供:
- IsotropicElastic: 各向同性线弹性 (Hooke's Law)
"""

import numpy as np
from typing import Tuple


class IsotropicElastic:
    """
    各向同性线弹性模型 (Hooke's Law)
    
    本构关系: σ = D : ε
    
    弹性矩阵 D 为 6x6 矩阵，使用 Voigt 记号:
    [σxx, σyy, σzz, σyz, σxz, σxy]^T = D @ [εxx, εyy, εzz, γyz, γxz, γxy]^T
    
    Attributes:
        E: 杨氏模量
        nu: 泊松比
        mu: 剪切模量 G = E / (2(1+ν))
        K: 体积模量 K = E / (3(1-2ν))
        lam: Lamé 第一参数 λ = Eν / ((1+ν)(1-2ν))
        D: 弹性矩阵 (6,6)
    
    Example:
        elastic = IsotropicElastic(E=210e9, nu=0.3)
        stress, tangent = elastic.compute_stress(strain_voigt)
    """
    
    def __init__(self, E: float, nu: float):
        """
        初始化各向同性弹性模型
        
        Args:
            E: 杨氏模量 (Young's modulus)
            nu: 泊松比 (Poisson's ratio), 需满足 -1 < ν < 0.5
        
        Raises:
            ValueError: 当泊松比超出有效范围时
        """
        if not (-1.0 < nu < 0.5):
            raise ValueError(f"Poisson's ratio must be in (-1, 0.5), got {nu}")
        
        self.E = float(E)
        self.nu = float(nu)
        
        # 计算导出参数
        self._mu = E / (2 * (1 + nu))
        self._K = E / (3 * (1 - 2 * nu))
        self._lam = E * nu / ((1 + nu) * (1 - 2 * nu))
        
        # 预计算弹性矩阵
        self._D = self._build_D_matrix()
    
    @property
    def mu(self) -> float:
        """剪切模量 G"""
        return self._mu
    
    @property
    def K(self) -> float:
        """体积模量 K"""
        return self._K
    
    @property
    def lam(self) -> float:
        """Lamé 第一参数 λ"""
        return self._lam
    
    @property
    def D(self) -> np.ndarray:
        """弹性矩阵 (6,6)"""
        return self._D
    
    def compute_stress(self, strain_voigt: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        计算弹性应力
        
        Args:
            strain_voigt: 工程应变 Voigt 向量 (6,)
                         [εxx, εyy, εzz, γyz, γxz, γxy]
        
        Returns:
            stress: 应力 Voigt 向量 (6,)
            tangent: 切线模量 (6,6)，对于弹性材料等于 D
        """
        stress = self._D @ strain_voigt
        return stress, self._D.copy()
    
    def _build_D_matrix(self) -> np.ndarray:
        """
        构建 6x6 弹性矩阵
        
        矩阵形式:
        | c1  c2  c2  0   0   0  |
        | c2  c1  c2  0   0   0  |
        | c2  c2  c1  0   0   0  |
        |  0   0   0  c3  0   0  |
        |  0   0   0   0  c3  0  |
        |  0   0   0   0   0  c3 |
        
        其中:
        - c1 = E(1-ν) / ((1+ν)(1-2ν))
        - c2 = Eν / ((1+ν)(1-2ν))
        - c3 = E / (2(1+ν)) = G (剪切模量)
        """
        E, nu = self.E, self.nu
        factor = E / ((1 + nu) * (1 - 2 * nu))
        
        c1 = (1 - nu) * factor
        c2 = nu * factor
        c3 = (1 - 2 * nu) / 2 * factor  # = G
        
        D = np.zeros((6, 6))
        
        # 正应力-正应变耦合
        D[0, 0] = D[1, 1] = D[2, 2] = c1
        D[0, 1] = D[0, 2] = D[1, 0] = D[1, 2] = D[2, 0] = D[2, 1] = c2
        
        # 剪切应力-剪切应变
        D[3, 3] = D[4, 4] = D[5, 5] = c3
        
        return D
    
    def __repr__(self) -> str:
        return f"IsotropicElastic(E={self.E:.2e}, nu={self.nu:.3f})"
