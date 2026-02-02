import numpy as np

class Quadrature:
    """
    数值积分模块
    对应 PDF 附录 A.5 gauspw.m 
    负责生成一维高斯积分点 (Gauss-Legendre integration points) 和权重。
    """

    @staticmethod
    def get_points(order):
        """
        根据积分阶数返回积分点坐标和权重。
        
        Args:
            order (int): 积分点的数量 (1, 2, or 3)
            
        Returns:
            points (np.array): 局部坐标 ξ 的位置列表
            weights (np.array): 对应的权重列表
        """
        if order == 1:
            # 1点积分：用于 SRI 的剪切项 (Shear Term) 
            # 坐标 = 0, 权重 = 2 (因为区间长度是 2) [cite: 1055]
            points = np.array([0.0])
            weights = np.array([2.0])
            
        elif order == 2:
            # 2点积分：用于 C3D8 标准全积分 (正应力项) [cite: 101]
            # 坐标 = ±1/sqrt(3) ≈ ±0.57735 [cite: 1059]
            # 权重 = 1.0 [cite: 1061]
            val = 1.0 / np.sqrt(3.0) # 0.577350269189626
            points = np.array([-val, val])
            weights = np.array([1.0, 1.0])
            
        elif order == 3:
            # 3点积分：更高精度的储备 
            # 坐标 = ±sqrt(0.6), 0
            # 权重 = 5/9, 8/9, 5/9 [cite: 1064]
            val = np.sqrt(0.6) # 0.774596669241483
            points = np.array([-val, 0.0, val])
            weights = np.array([5.0/9.0, 8.0/9.0, 5.0/9.0])
            
        else:
            raise ValueError(f"Integration order {order} not supported yet.")
            
        return points, weights

