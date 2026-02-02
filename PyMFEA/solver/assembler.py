import numpy as np
from scipy.sparse import coo_matrix

class GlobalAssembler:
    """
    全局刚度矩阵组装器
    对应 PDF: gstiffm_3d8n.m
    使用 COO (Coordinate) 格式高效构建稀疏矩阵
    """
    
    def __init__(self, elements, num_nodes):
        """
        Args:
            elements (list): 包含所有 Element 对象的列表
            num_nodes (int): 网格中的总节点数 (用于确定矩阵大小)
        """
        self.elements = elements
        self.num_nodes = num_nodes
        self.total_dof = num_nodes * 3  # 每个节点 3 个自由度 (u, v, w)

    def assemble(self):
        """
        执行组装过程（线性模式）
        Returns:
            K_global (scipy.sparse.csr_matrix): 压缩稀疏行格式的全局刚度矩阵
        """
        # 使用通用组装接口，传入线性单元计算回调
        def linear_element_routine(elem, u_current):
            Ke = elem.calc_Ke()
            return Ke, None, False  # (K, F_int, failed)
        
        K_global, _, _ = self.assemble_generic(linear_element_routine, u_current=None)
        return K_global
    
    def assemble_generic(self, element_routine, u_current=None):
        """
        通用稀疏矩阵组装方法
        
        支持两种模式：
        1. 线性模式：仅返回全局刚度矩阵 K
        2. 非线性模式：同时返回全局切线刚度矩阵 K 和全局内力向量 F_int
        
        Args:
            element_routine (callable): 单元计算回调函数
                签名: element_routine(elem, u_current) -> (Ke, Fe, failed)
                - elem: 单元对象
                - u_current: 当前位移向量（可选，线性模式下为None）
                返回:
                - Ke (24x24): 单元刚度矩阵
                - Fe (24,): 单元内力向量（线性模式下为None）
                - failed (bool): 计算是否失败
            u_current (np.ndarray, optional): 当前全局位移向量（非线性模式需要）
        
        Returns:
            K_global (scipy.sparse.csr_matrix): 全局刚度矩阵
            F_int_global (np.ndarray or None): 全局内力向量（线性模式下为None）
            assembly_failed (bool): 组装是否失败
        """
        num_elem = len(self.elements)
        # C3D8 单元每个有 24 个自由度，矩阵大小为 24x24 = 576 个元素
        entries_per_elem = 24 * 24 
        total_entries = num_elem * entries_per_elem
        
        # 1. 预分配 NumPy 数组 (Pre-allocation)
        # 对应 PDF gstiffm_3d8n.m lines 5-6 
        # 避免在循环中动态调整数组大小，这是高性能的关键
        rows = np.zeros(total_entries, dtype=np.int32)
        cols = np.zeros(total_entries, dtype=np.int32)
        data = np.zeros(total_entries, dtype=np.float64)
        
        # 内力向量（仅非线性模式需要）
        F_int_global = np.zeros(self.total_dof)
        
        ptr = 0  # 指针，记录当前填到了哪个位置
        assembly_failed = False
        
        print(f"开始组装全局刚度矩阵... (单元数: {num_elem}, 总DOF: {self.total_dof})")
        
        # 2. 遍历所有单元
        for elem in self.elements:
            # 调用单元计算回调函数
            # 对应 PDF: estiffm_3d8n.m 调用（线性）或非线性单元的 compute_element
            Ke, Fe, failed = element_routine(elem, u_current)
            
            if failed:
                assembly_failed = True
                break
            
            # 获取该单元的全局自由度索引 (1x24)
            # 对应 PDF gstiffm_3d8n.m lines 28-33 [cite: 1237-1248]
            dofs = elem.get_dof_indices()
            
            # 3. 组装内力向量（如果有）
            if Fe is not None:
                # 利用 NumPy 高级索引直接累加
                F_int_global[dofs] += Fe
            
            # 4. 构建索引网格
            # r_grid, c_grid 类似于 MATLAB 的 meshgrid
            # 对应 PDF gstiffm_3d8n.m line 34 [cite: 1251]
            # indexing='ij' 确保顺序与 Ke.flatten() 匹配
            r_grid, c_grid = np.meshgrid(dofs, dofs, indexing='ij')
            
            # 5. 填充数据到大数组
            # 对应 PDF gstiffm_3d8n.m lines 38-40 [cite: 1260-1267]
            end_ptr = ptr + entries_per_elem
            
            rows[ptr:end_ptr] = r_grid.flatten()
            cols[ptr:end_ptr] = c_grid.flatten()
            data[ptr:end_ptr] = Ke.flatten()
            
            ptr = end_ptr
        
        if assembly_failed:
            return None, None, True
            
        # 6. 创建稀疏矩阵
        # 对应 PDF gstiffm_3d8n.m line 43 [cite: 1275]
        # coo_matrix 会自动处理重复索引的累加 (Assembly by summation)
        K_coo = coo_matrix((data, (rows, cols)), shape=(self.total_dof, self.total_dof))
        
        # 转换为 CSR (Compressed Sparse Row) 格式，更适合线性方程组求解
        K_csr = K_coo.tocsr()
        
        print("全局刚度矩阵组装完成。")
        
        # 返回内力向量（线性模式下返回None）
        F_int_result = F_int_global if u_current is not None else None
        return K_csr, F_int_result, False

