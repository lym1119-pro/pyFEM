import numpy as np
from abc import ABC, abstractmethod
from .quadrature import Quadrature

class BaseElement(ABC):
    """
    有限元单元抽象基类。
    定义所有单元类型的通用属性和接口，处理节点、材料及自由度索引。
    """
    def __init__(self, element_id, nodes, material, dofs_per_node=3):
        """
        初始化单元基础属性。
        
        Args:
            element_id (int): 单元唯一标识 ID
            nodes (list): 节点对象列表 (需具备 coords 属性)
            material (Material): 材料对象 (需具备 D_matrix 属性)
            dofs_per_node (int): 每个节点的自由度数量
        """
        self.id = element_id
        self.nodes = nodes
        self.material = material
        self.dofs_per_node = dofs_per_node
        
        # 预先提取节点坐标矩阵，优化后续计算效率
        self.node_coords_matrix = np.array([n.coords for n in nodes])

    def get_dof_indices(self):
        """
        根据节点 ID 自动生成全局自由度索引列表。
        适用于大多数连续体单元的通用组装逻辑。
        """
        dofs = []
        for node in self.nodes:
            # 计算起始自由度：(节点ID - 1) * 节点自由度数
            start = (node.id - 1) * self.dofs_per_node
            # 按顺序添加该节点的所有自由度
            dofs.extend(range(start, start + self.dofs_per_node))
        return np.array(dofs, dtype=int)

    @abstractmethod
    def _calc_shape_functions(self, *args):
        """抽象方法：计算形函数值及其局部导数。"""
        pass

    @abstractmethod
    def _calc_B_matrix(self, *args):
        """抽象方法：计算应变-位移矩阵 B 和雅可比行列式。"""
        pass

    @abstractmethod
    def calc_Ke(self):
        """抽象方法：执行数值积分以计算单元刚度矩阵。"""
        pass


class C3D8Element(BaseElement):
    """
    标准 8 节点六面体单元 (C3D8)。
    采用 2×2×2 高斯点全积分，适配 3D 线性弹性分析。
    """
    def __init__(self, element_id, nodes, material):
        # 显式初始化父类，设定 C3D8 节点的自由度数为 3
        super().__init__(element_id, nodes, material, dofs_per_node=3)
        
    def _calc_shape_functions(self, xi, eta, zeta):
        """
        计算局部坐标 (xi, eta, zeta) 处的三线性插值形函数。
        
        Returns:
            N: 形函数向量 (8,)
            dN_dxi: 局部导数矩阵 (3, 8)
        """
        # 预计算位置变量
        rp, rm = 1 + xi, 1 - xi
        sp, sm = 1 + eta, 1 - eta
        tp, tm = 1 + zeta, 1 - zeta
        
        # 1. 计算 8 个形函数的值
        N = 0.125 * np.array([
            rm * sm * tm, rp * sm * tm, rp * sp * tm, rm * sp * tm,
            rm * sm * tp, rp * sm * tp, rp * sp * tp, rm * sp * tp
        ])
        
        # 2. 计算形函数对局部坐标 (xi, eta, zeta) 的偏导数
        dN_dxi = np.zeros((3, 8))
        
        # dN/dxi
        dN_dxi[0, :] = 0.125 * np.array([
            -(sm * tm), (sm * tm), (sp * tm), -(sp * tm),
            -(sm * tp), (sm * tp), (sp * tp), -(sp * tp)
        ])
        # dN/deta
        dN_dxi[1, :] = 0.125 * np.array([
            -(rm * tm), -(rp * tm), (rp * tm), (rm * tm),
            -(rm * tp), -(rp * tp), (rp * tp), (rm * tp)
        ])
        # dN/dzeta
        dN_dxi[2, :] = 0.125 * np.array([
            -(rm * sm), -(rp * sm), -(rp * sp), -(rm * sp),
            (rm * sm),  (rp * sm),  (rp * sp),  (rm * sp)
        ])
        
        return N, dN_dxi

    def _calc_B_matrix(self, xi, eta, zeta):
        """
        计算应变-位移矩阵 B (6×24) 与雅可比行列式 detJ。
        """
        # 1. 获取局部导数并计算雅可比矩阵 J (3x3)
        _, dN_dlocal = self._calc_shape_functions(xi, eta, zeta)
        J = dN_dlocal @ self.node_coords_matrix
        
        # 2. 计算雅可比行列式并校验单元是否畸形
        detJ = np.linalg.det(J)
        if detJ <= 0:
            raise ValueError(f"单元 {self.id} 在局部坐标 ({xi},{eta},{zeta}) 处雅可比行列式非正。")
            
        # 3. 计算全局坐标偏导数 dN/dx = inv(J) * dN/dlocal
        J_inv = np.linalg.inv(J)
        dN_dglobal = J_inv @ dN_dlocal
        
        # 4. 组装应变矩阵 B (6x24)
        B = np.zeros((6, 24))
        for i in range(8):
            col_start = 3 * i
            dx, dy, dz = dN_dglobal[0, i], dN_dglobal[1, i], dN_dglobal[2, i]
            
            # 正应变分量 (xx, yy, zz)
            B[0, col_start]     = dx
            B[1, col_start + 1] = dy
            B[2, col_start + 2] = dz
            # 剪切应变分量 (xy, yz, zx)
            B[3, col_start]     = dy
            B[3, col_start + 1] = dx
            B[4, col_start + 1] = dz
            B[4, col_start + 2] = dy
            B[5, col_start]     = dz
            B[5, col_start + 2] = dx
            
        return B, detJ

    def calc_Ke(self):
        """
        执行数值积分，计算单元刚度矩阵 Ke (24x24)。
        """
        Ke = np.zeros((24, 24))
        D = self.material.D_matrix
        
        # 获取 2x2x2 高斯积分点和权重
        points, weights = Quadrature.get_points(order=2)
        
        for i, xi in enumerate(points):
            for j, eta in enumerate(points):
                for k, zeta in enumerate(points):
                    # 组合三重积分权重
                    w_total = weights[i] * weights[j] * weights[k]
                    
                    # 获取该点处的 B 矩阵和雅可比行列式
                    B, detJ = self._calc_B_matrix(xi, eta, zeta)
                    
                    # 累加刚度矩阵贡献：Ke = ∑ B.T * D * B * detJ * weight
                    Ke += (B.T @ D @ B) * detJ * w_total
                    
        return Ke