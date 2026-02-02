# 文件: PyMFEA/core/materials/factory.py
"""
材料工厂模块

提供统一的材料创建入口。
"""

from typing import Dict, Any, Optional
from .interfaces import Material
from .models.j2_plasticity import J2PlasticMaterial


class MaterialFactory:
    """
    材料工厂
    
    根据材料属性字典创建对应的材料对象。
    提供便捷的工厂方法简化常见材料的创建。
    
    Example:
        # 从属性字典创建
        mat = MaterialFactory.create('Steel', {
            'E': 210e9, 
            'nu': 0.3, 
            'plastic': {'yield_stress': 250e6}
        })
        
        # 使用便捷方法
        mat = MaterialFactory.create_elastic(E=210e9, nu=0.3)
        mat = MaterialFactory.create_j2_plastic(E=210e9, nu=0.3, yield_stress=250e6)
    """
    
    @staticmethod
    def create(name: str, props: Dict[str, Any]) -> Material:
        """
        根据属性字典创建材料
        
        Args:
            name: 材料名称 (用于错误消息)
            props: 材料属性字典，结构:
                {
                    'E': float,          # 杨氏模量 (必需)
                    'nu': float,         # 泊松比 (必需)
                    'density': float,    # 密度 (可选)
                    'plastic': {         # 塑性参数 (可选)
                        'yield_stress': float,
                        'hardening': float  # 默认 0
                    }
                }
                
        Returns:
            Material: 材料对象
            
        Raises:
            ValueError: 缺少必需参数
        """
        # 检查必需参数
        E = props.get('E')
        nu = props.get('nu')
        
        if E is None or nu is None:
            raise ValueError(
                f"Material '{name}' missing required parameters. "
                f"Got E={E}, nu={nu}"
            )
        
        # 检查塑性参数
        plastic = props.get('plastic')
        
        if plastic is not None:
            yield_stress = plastic.get('yield_stress')
            if yield_stress is None:
                raise ValueError(
                    f"Material '{name}' has plastic section but missing 'yield_stress'"
                )
            
            hardening = plastic.get('hardening', 0.0)
            
            # --- 数值硬化 (Numerical Hardening) ---
            # 即使对于理想塑性，也施加极小的硬化模量
            # 以防止刚度矩阵在塑性流动时变得奇异
            min_hardening = float(E) * 1e-4
            if hardening < min_hardening:
                hardening = min_hardening
            
            return J2PlasticMaterial(
                E=float(E),
                nu=float(nu),
                yield_stress=float(yield_stress),
                hardening=float(hardening)
            )
        else:
            # 纯弹性材料：使用无限大屈服应力
            return J2PlasticMaterial(
                E=float(E),
                nu=float(nu),
                yield_stress=1e30  # 实际上永远不会屈服
            )
    
    @staticmethod
    def create_elastic(E: float, nu: float) -> Material:
        """
        创建纯弹性材料
        
        Args:
            E: 杨氏模量
            nu: 泊松比
            
        Returns:
            J2PlasticMaterial: 设置为纯弹性响应
        """
        return J2PlasticMaterial(E=E, nu=nu, yield_stress=1e30)
    
    @staticmethod
    def create_j2_plastic(
        E: float, 
        nu: float, 
        yield_stress: float, 
        hardening: float = 0.0
    ) -> J2PlasticMaterial:
        """
        创建 J2 弹塑性材料
        
        Args:
            E: 杨氏模量
            nu: 泊松比
            yield_stress: 初始屈服应力
            hardening: 硬化模量 (0 表示理想塑性)
            
        Returns:
            J2PlasticMaterial: J2 弹塑性材料
        """
        # 数值硬化
        min_hardening = E * 1e-4
        if hardening < min_hardening:
            hardening = min_hardening
            
        return J2PlasticMaterial(
            E=E,
            nu=nu,
            yield_stress=yield_stress,
            hardening=hardening
        )
    
    @staticmethod
    def create_perfect_plastic(
        E: float, 
        nu: float, 
        yield_stress: float
    ) -> J2PlasticMaterial:
        """
        创建理想弹塑性材料 (带数值硬化)
        
        Args:
            E: 杨氏模量
            nu: 泊松比
            yield_stress: 屈服应力
            
        Returns:
            J2PlasticMaterial: 理想弹塑性材料
        """
        # 强制使用数值硬化
        hardening = E * 1e-4
        
        return J2PlasticMaterial(
            E=E,
            nu=nu,
            yield_stress=yield_stress,
            hardening=hardening
        )
