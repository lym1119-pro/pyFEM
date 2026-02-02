# 文件路径: PyMFEA/gui/model_tree.py
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, 
                             QTreeWidgetItem, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QBrush, QColor

class ModelTreeWidget(QWidget):
    """
    仿截图风格的模型树：双列显示 (Type | Size)
    显示 Node/Element 数量统计，支持 Nset/Eset/Surface 列表
    """
    # 信号：请求查看数据 (payload 包含数据类型和名称)
    item_edit_requested = pyqtSignal(dict)
    
    # 信号：为了兼容 app.py 的旧接口，保留这些信号，即使暂时不用
    create_requested = pyqtSignal(dict)
    edit_requested = pyqtSignal(dict)
    rename_requested = pyqtSignal(dict)
    delete_requested = pyqtSignal(dict)
    set_active_requested = pyqtSignal(dict)
    object_activated = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- 树形控件配置 ---
        self.tree = QTreeWidget()
        
        # 1. 设置两列：Type (名称) 和 Size (数量)
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["type", "size"])
        
        # 2. 调整列宽行为
        header = self.tree.header()
        # 禁用用户手动调整列宽，确保固定宽度生效
        header.setSectionsMovable(False)
        # 第 0 列 (Type/Name) 自动拉伸占据主要宽度
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        # 第 1 列 (Count/Info) 使用固定宽度，保持紧凑，紧贴右侧
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 60)  # 设置固定宽度为 60px
        header.setDefaultAlignment(Qt.AlignLeft)

        # 3. 样式表 (仿截图风格：灰色表头，白色背景，选中变蓝)
        # 通过 QSS 增加 Item 的行高和内边距，优化双列显示
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #A0A0A0;
                background-color: #ffffff;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                font-size: 10pt;
                alternate-background-color: #F8F8F8;
            }
            QHeaderView::section {
                background-color: #DDDDDD; /* 工业灰表头 */
                color: #333333;
                padding: 6px 8px; /* 增加表头内边距 */
                border: 1px solid #A0A0A0;
                border-bottom: 2px solid #808080;
                font-weight: bold;
                font-size: 10pt;
                height: 32px; /* 增加表头高度 */
            }
            QTreeWidget::item {
                height: 32px; /* 增加行高，提升可读性 */
                padding: 6px 8px; /* 增加内边距（上下6px，左右8px） */
                border-bottom: 1px solid #F0F0F0;
            }
            QTreeWidget::item:hover {
                background-color: #E8F4FD; /* 悬停时浅蓝色背景 */
            }
            /* 选中行的颜色 */
            QTreeWidget::item:selected {
                background-color: #A0C4E8; 
                color: #000000;
            }
            QTreeWidget::item:selected:active {
                background-color: #8FBCDB;
            }
        """)
        
        # 4. 交互设置
        self.tree.setSelectionBehavior(QTreeWidget.SelectRows) # 整行选中
        self.tree.setAlternatingRowColors(False)
        
        # 连接双击信号
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        layout.addWidget(self.tree)

    def update_structure(self, database):
        """
        根据 INP 解析数据刷新树结构
        database: utils.inp_reader.InpParser 解析出的字典
        """
        self.tree.clear()
        
        # 设置字体 - 使用 Segoe UI 10pt，与全局字体保持一致
        font_root = QFont("Segoe UI", 10)
        
        # --- 根节点 Model-1 ---
        root = QTreeWidgetItem(self.tree)
        root.setText(0, "Model-1")
        root.setFont(0, font_root)
        root.setExpanded(True)
        
        if not database:
            return

        # 从数据库字典中获取各类数据
        nodes = database.get('nodes', {})
        elements = database.get('elements', {})
        nsets = database.get('nsets', {})
        elsets = database.get('elsets', {})
        surfaces = database.get('surfaces', {})
        materials = database.get('materials', {})
        constraints = database.get('constraints', [])
        loads = database.get('loads', [])

        # === 1. Node (显示节点总数) ===
        item_node = QTreeWidgetItem(root)
        item_node.setText(0, "Node")
        item_node.setText(1, str(len(nodes)))
        # 绑定数据用于双击查看表格
        item_node.setData(0, Qt.UserRole, {"category": "mesh", "name": "Nodes"})

        # === 2. Element (显示单元总数) ===
        item_elem = QTreeWidgetItem(root)
        item_elem.setText(0, "Element")
        item_elem.setText(1, str(len(elements)))
        item_elem.setData(0, Qt.UserRole, {"category": "mesh", "name": "Elements"})

        # === 3. Sets (集合分类) ===
        item_sets = QTreeWidgetItem(root)
        item_sets.setText(0, "Sets")
        total_sets = len(nsets) + len(elsets) + len(surfaces)
        item_sets.setText(1, str(total_sets))
        item_sets.setExpanded(True)
        
        # 3.1 Nset (节点集合)
        item_nset = QTreeWidgetItem(item_sets)
        item_nset.setText(0, "Nset")
        item_nset.setText(1, str(len(nsets)))
        item_nset.setExpanded(True)
        
        for name, ids in nsets.items():
            child = QTreeWidgetItem(item_nset)
            child.setText(0, name)
            child.setText(1, str(len(ids))) # 只有两列，Size 列显示包含的ID数量
            # 绑定 Set 数据
            child.setData(0, Qt.UserRole, {"category": "nset", "name": name, "ids": ids})

        # 3.2 Eset (单元集合)
        item_eset = QTreeWidgetItem(item_sets)
        item_eset.setText(0, "Eset")
        item_eset.setText(1, str(len(elsets)))
        item_eset.setExpanded(True)

        for name, ids in elsets.items():
            child = QTreeWidgetItem(item_eset)
            child.setText(0, name)
            child.setText(1, str(len(ids)))
            child.setData(0, Qt.UserRole, {"category": "elset", "name": name, "ids": ids})

        # 3.3 Surface (表面)
        item_surf = QTreeWidgetItem(item_sets)
        item_surf.setText(0, "Surface")
        item_surf.setText(1, str(len(surfaces)))
        item_surf.setExpanded(True)
        
        for name, faces in surfaces.items():
            child = QTreeWidgetItem(item_surf)
            child.setText(0, name)
            child.setText(1, str(len(faces))) # 面定义的数量

        # === 4. Materials (材料分类) ===
        if materials:
            item_materials = QTreeWidgetItem(root)
            item_materials.setText(0, "Materials")
            item_materials.setText(1, str(len(materials)))
            item_materials.setExpanded(True)
            
            for mname, mat_data in materials.items():
                child = QTreeWidgetItem(item_materials)
                child.setText(0, mname)
                # 显示材料信息：E, nu, density
                info_parts = []
                if mat_data.get('E') is not None:
                    info_parts.append(f"E={mat_data['E']:.0f}")
                if mat_data.get('nu') is not None:
                    info_parts.append(f"ν={mat_data['nu']:.2f}")
                if mat_data.get('density') is not None:
                    info_parts.append(f"ρ={mat_data['density']:.2f}")
                child.setText(1, ", ".join(info_parts) if info_parts else "")
                # 绑定材料数据
                child.setData(0, Qt.UserRole, {"category": "material", "name": mname, "data": mat_data})
        
        # === 4.1 Properties (属性分类) - 保留用于其他属性 ===
        item_props = QTreeWidgetItem(root)
        item_props.setText(0, "Properties")
        item_props.setText(1, "0")
        item_props.setExpanded(True)

        # === 5. BC (边界条件 + 载荷) ===
        total_bc = len(constraints) + len(loads)
        item_bc = QTreeWidgetItem(root)
        item_bc.setText(0, "BC")
        item_bc.setText(1, str(total_bc))
        item_bc.setExpanded(True)
        
        # 列出 Constraints (Fix)
        for i, bc in enumerate(constraints):
            child = QTreeWidgetItem(item_bc)
            # 检查是set还是节点
            if 'set_name' in bc:
                child.setText(0, f"Fix-Set:{bc['set_name']}")
            elif 'node_id' in bc:
                child.setText(0, f"Fix-Node{bc['node_id']}")
            else:
                child.setText(0, "Fix")
            child.setText(1, f"DOF:{bc['dof']+1}") # 显示自由度
            
        # 列出 Loads (Force/Pressure)
        # 过滤掉从surface展开的节点力，只显示surface信息
        displayed_loads = []
        surface_loads_seen = set()
        
        for ld in loads:
            # 如果是surface载荷，直接显示
            if 'surface_name' in ld:
                displayed_loads.append(ld)
                surface_loads_seen.add(ld['surface_name'])
            # 如果是set载荷，直接显示
            elif 'set_name' in ld:
                displayed_loads.append(ld)
            # 如果是节点载荷，但来自surface，跳过（已在surface中显示）
            elif 'node_id' in ld and 'from_surface' in ld:
                # 跳过，因为已经在surface中显示了
                continue
            # 如果是普通节点载荷，显示
            elif 'node_id' in ld:
                displayed_loads.append(ld)
            else:
                displayed_loads.append(ld)
        
        for i, ld in enumerate(displayed_loads):
            child = QTreeWidgetItem(item_bc)
            # 检查是surface、set还是节点
            if 'surface_name' in ld:
                child.setText(0, f"Load-Surface:{ld['surface_name']}")
                child.setText(1, f"{ld.get('type', 'Pressure')}:{ld['value']:.1f}")
            elif 'set_name' in ld:
                child.setText(0, f"Load-Set:{ld['set_name']}")
                child.setText(1, f"DOF:{ld['dof']+1}, Val:{ld['value']:.1f}")
            elif 'node_id' in ld:
                child.setText(0, f"Load-Node{ld['node_id']}")
                child.setText(1, f"DOF:{ld['dof']+1}, Val:{ld['value']:.1f}")
            else:
                child.setText(0, "Load")
                child.setText(1, f"Val:{ld.get('value', 0):.1f}")

        # === 8. Field & Job (静态占位) ===
        QTreeWidgetItem(root, ["Field", ""])
        QTreeWidgetItem(root, ["Job", ""])
        
        # 默认展开根节点
        self.tree.expandItem(root)
        
        # 数据加载后，使用 QTimer 延迟设置列宽，确保在界面渲染后生效
        QTimer.singleShot(0, self._apply_column_widths)
    
    def _apply_column_widths(self):
        """应用列宽设置，确保第 1 列固定为 60px"""
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 60)  # 强制设置第 1 列为 60px

    def on_item_double_clicked(self, item, column):
        """双击事件转发给主窗口"""
        payload = item.data(0, Qt.UserRole)
        if isinstance(payload, dict):
            # 发送信号，MainWindow 接收后弹出表格
            self.item_edit_requested.emit(payload)