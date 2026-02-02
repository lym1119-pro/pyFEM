import numpy as np

class Node:
    """
    有限元节点类。

    负责存储节点的全局 ID 以及三维空间坐标 (x, y, z)，
    不包含自由度、载荷等信息，这些由装配器／求解器按照约定计算。
    """
    def __init__(self, node_id, x, y, z):
        self.id = int(node_id)
        self.coords = np.array([float(x), float(y), float(z)])
        
    def __repr__(self):
        return f"Node({self.id}, {self.coords})"