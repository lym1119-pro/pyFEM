"""
PyAbaqus/CAE - 模拟Abaqus界面
包含：菜单栏、工具栏、模型树、工具箱、3D视口、消息窗口
"""
import sys
import subprocess
import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFrame, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QTextEdit, QWidget,
    QSlider, QSplitter, QToolBar, QStatusBar, QProgressBar, QGroupBox,
    QSizePolicy, QInputDialog, QDockWidget, QTreeWidget, QTreeWidgetItem,
    QPlainTextEdit, QLineEdit, QHBoxLayout, QVBoxLayout, QGridLayout,
    QSpacerItem, QSizePolicy, QDoubleSpinBox, QCheckBox, QToolButton,
    QScrollArea
)
from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor, QLinearGradient, QBrush
from PyQt5.QtWidgets import QStyle
# 在 app.py 顶部导入区域添加或修改：
from gui.model_tree import ModelTreeWidget
from gui.dialogs import DataViewerDialog  # <--- 新增这行
from gui.worker import SolverWorker
from gui.model_tree import ModelTreeWidget
from gui.icons import icon_manager
from PyQt5.QtWidgets import QMessageBox, QDialog
from gui.dialogs import DataViewerDialog, SolverSettingsDialog

class MainWindow(QMainWindow):
    """主窗口 - 模拟Abaqus/CAE"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyFEMEA - Finite Element Analysis Platform")
        self.setMinimumSize(1280, 800)
        self.resize(1280, 800)

        # 样式表已在 main.py 中全局应用，无需在此处重复设置

        # 数据缓存
        self.inp_data = None
        self.material_props = {"E": 70000.0, "nu": 0.3}
        self.current_mesh = None
        self.current_disp = None
        self.current_stress = None
        self.current_stress_components = None  # 应力分量
        self.current_object = None  # 当前激活的 Part / Assembly 等对象
        # 线程管理
        self.worker = None  # 工作线程引用
        self.monitor_dialog = None  # 监控对话框引用
        
        # 监控数据缓存（用于求解完成后查看历史记录）
        self.monitor_data = {
            'log_messages': [],  # 日志消息列表
            'iterations': [],    # 迭代次数列表
            'residuals': [],     # 残差值列表
            'status_history': [], # 状态历史
            'progress': 0,        # 最终进度
            'is_completed': False # 是否已完成
        }
        # BC 和 Load 可视化相关
        self.bc_load_actors = []  # 存储 BC 和 Load 的 Actor 引用
        self.show_bc_loads = False  # 是否显示 BC 和 Load
        # Abaqus 接口相关状态
        self.abaqus_inp_path = None         # 用户选择的 INP 文件保存路径（目录）
        self.abaqus_executable = None        # Abaqus 可执行文件路径（缓存，避免每次都查找）
        self.abaqus_waiting_for_import = False  # 是否处于"等待导入"状态
        # 结果类型映射（界面显示 -> 网格字段名）
        self.result_type_map = {
            "VonMises": "VonMises",
            "Displacement": "Displacement",
            "S11 (σx)": "S11",
            "S22 (σy)": "S22",
            "S33 (σz)": "S33",
            "S12 (τxy)": "S12",
            "S23 (τyz)": "S23",
            "S13 (τxz)": "S13",
        }

        # 初始化图标管理器
        icon_manager.set_style(self.style())
        
        # 设置窗口图标
        self.setWindowIcon(icon_manager.app_icon(32))
        
        # 创建UI组件
        self.create_menu_bar()
        self.create_toolbar()
        self.create_context_bar()
        self.create_statusbar()
        self.create_dock_widgets()
        self.create_central_widget()
        self.create_bottom_area()
        
        # 连接模块切换
        self.module_combo.currentIndexChanged.connect(self.on_module_changed)
        self.on_module_changed()  # 初始化
        
        # 使用 QTimer 在窗口显示后设置 DockWidget 的初始大小
        QTimer.singleShot(100, self._set_initial_dock_sizes)
        
        
    def create_menu_bar(self):
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # File
        file_menu = menubar.addMenu('File')
        file_menu.addAction(icon_manager.new_file(), 'New Model Database').triggered.connect(self.new_model_database)
        file_menu.addAction(icon_manager.open_file(), 'Open').triggered.connect(self.open_file)
        file_menu.addAction(icon_manager.save_file(), 'Save').triggered.connect(self.save_file)
        file_menu.addSeparator()
        file_menu.addAction(icon_manager.import_file(), 'Import').triggered.connect(self.import_file)
        file_menu.addAction(icon_manager.export_file(), 'Export').triggered.connect(self.export_file)
        file_menu.addSeparator()
        file_menu.addAction(icon_manager.exit(), 'Exit').triggered.connect(self.close)
        
        # Model
        model_menu = menubar.addMenu('Model')
        model_menu.addAction(icon_manager.create_part(), 'Create').triggered.connect(self.create_model)
        model_menu.addAction('Copy').triggered.connect(self.copy_model)
        model_menu.addAction('Rename').triggered.connect(self.rename_model)
        model_menu.addAction('Delete').triggered.connect(self.delete_model)
        
        # Viewport
        viewport_menu = menubar.addMenu('Viewport')
        viewport_menu.addAction('Create Viewport').triggered.connect(self.create_viewport)
        viewport_menu.addAction('Delete Viewport').triggered.connect(self.delete_viewport)
        viewport_menu.addAction('Tile Viewports').triggered.connect(self.tile_viewports)
        
        # View
        view_menu = menubar.addMenu('View')
        view_menu.addAction(icon_manager.view_front(), 'Front').triggered.connect(self.view_front)
        view_menu.addAction(icon_manager.view_back(), 'Back').triggered.connect(self.view_back)
        view_menu.addAction(icon_manager.view_left(), 'Left').triggered.connect(self.view_left)
        view_menu.addAction(icon_manager.view_right(), 'Right').triggered.connect(self.view_right)
        view_menu.addAction(icon_manager.view_top(), 'Top').triggered.connect(self.view_top)
        view_menu.addAction(icon_manager.view_bottom(), 'Bottom').triggered.connect(self.view_bottom)
        view_menu.addAction(icon_manager.view_iso(), 'Iso').triggered.connect(self.view_iso)
        view_menu.addSeparator()
        view_menu.addAction(icon_manager.reset_view(), 'Reset View').triggered.connect(self.reset_view)
        view_menu.addAction(icon_manager.zoom_fit(), 'Fit View').triggered.connect(self.fit_view)
        view_menu.addAction(icon_manager.zoom_in(), 'Zoom In').triggered.connect(lambda: self.message_area.appendPlainText("Zoom In\n"))
        view_menu.addAction(icon_manager.zoom_out(), 'Zoom Out').triggered.connect(lambda: self.message_area.appendPlainText("Zoom Out\n"))
        
        # Part
        part_menu = menubar.addMenu('Part')
        part_menu.addAction(icon_manager.create_part(), 'Create').triggered.connect(self.create_part)
        part_menu.addAction('Edit').triggered.connect(self.edit_part)
        
        # Shape
        shape_menu = menubar.addMenu('Shape')
        shape_menu.addAction('Extrude').triggered.connect(self.extrude_shape)
        shape_menu.addAction('Revolve').triggered.connect(self.revolve_shape)
        
        # Feature
        feature_menu = menubar.addMenu('Feature')
        feature_menu.addAction('Fillet').triggered.connect(self.create_fillet)
        feature_menu.addAction('Chamfer').triggered.connect(self.create_chamfer)
        
        # Tools
        tools_menu = menubar.addMenu('Tools')
        tools_menu.addAction(icon_manager.query(), 'Query').triggered.connect(self.query_tool)
        tools_menu.addAction(icon_manager.measure(), 'Measure').triggered.connect(self.measure_tool)
        # Abaqus 建模交互（两步：启动 -> 导入）
        self.abaqus_action = tools_menu.addAction('Abaqus Modeling...')
        self.abaqus_action.triggered.connect(self.launch_abaqus_cae)
        
        # Plug-ins
        plugins_menu = menubar.addMenu('Plug-ins')
        plugins_menu.addAction('Manager').triggered.connect(self.plugin_manager)
        
        # Help
        help_menu = menubar.addMenu('Help')
        help_menu.addAction(icon_manager.help(), 'On Context').triggered.connect(self.help_context)
        help_menu.addAction(icon_manager.about(), 'About Abaqus/CAE').triggered.connect(self.about)
        
    def create_toolbar(self):
        """创建主工具栏（文件 + 视图）"""
        main_toolbar = QToolBar("Main Toolbar")
        main_toolbar.setMovable(False)
        main_toolbar.setAllowedAreas(Qt.TopToolBarArea)
        main_toolbar.setIconSize(QSize(40, 40))
        self.addToolBar(main_toolbar)

        # 文件操作（左侧）
        btn_new = QToolButton()
        btn_new.setIcon(icon_manager.new_file())
        btn_new.setToolTip("New Model Database")
        btn_new.clicked.connect(self.new_model_database)
        main_toolbar.addWidget(btn_new)

        btn_open = QToolButton()
        btn_open.setIcon(icon_manager.open_file())
        btn_open.setToolTip("Open INP File")
        btn_open.clicked.connect(self.open_file)
        main_toolbar.addWidget(btn_open)

        btn_save = QToolButton()
        btn_save.setIcon(icon_manager.save_file())
        btn_save.setToolTip("Save")
        btn_save.clicked.connect(self.save_file)
        main_toolbar.addWidget(btn_save)

        main_toolbar.addSeparator()

        btn_import = QToolButton()
        btn_import.setIcon(icon_manager.import_file())
        btn_import.setToolTip("Import")
        btn_import.clicked.connect(self.import_file)
        main_toolbar.addWidget(btn_import)

        btn_export = QToolButton()
        btn_export.setIcon(icon_manager.export_file())
        btn_export.setToolTip("Export")
        btn_export.clicked.connect(self.export_file)
        main_toolbar.addWidget(btn_export)

        # 视图操作（靠右侧对齐的经典 Abaqus 风格）
        main_toolbar.addSeparator()

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        main_toolbar.addWidget(spacer)

        btn_view_iso = QToolButton()
        btn_view_iso.setIcon(icon_manager.view_iso())
        btn_view_iso.setToolTip("Isometric View")
        btn_view_iso.clicked.connect(self.view_iso)
        main_toolbar.addWidget(btn_view_iso)

        btn_view_front = QToolButton()
        btn_view_front.setIcon(icon_manager.view_front())
        btn_view_front.setToolTip("Front View")
        btn_view_front.clicked.connect(self.view_front)
        main_toolbar.addWidget(btn_view_front)

        btn_view_top = QToolButton()
        btn_view_top.setIcon(icon_manager.view_top())
        btn_view_top.setToolTip("Top View")
        btn_view_top.clicked.connect(self.view_top)
        main_toolbar.addWidget(btn_view_top)

        main_toolbar.addSeparator()

        btn_reset = QToolButton()
        btn_reset.setIcon(icon_manager.reset_view())
        btn_reset.setToolTip("Reset View")
        btn_reset.clicked.connect(self.reset_view)
        main_toolbar.addWidget(btn_reset)

        btn_fit = QToolButton()
        btn_fit.setIcon(icon_manager.zoom_fit())
        btn_fit.setToolTip("Fit View")
        btn_fit.clicked.connect(self.fit_view)
        main_toolbar.addWidget(btn_fit)

    def create_context_bar(self):
        """创建 Abaqus 风格的 Context Bar（第二行上下文导航工具栏）"""
        context_bar = QToolBar("Context Bar")
        context_bar.setAllowedAreas(Qt.TopToolBarArea)
        context_bar.setMovable(False)
        # 再略加高度，让这一条更饱满一些
        context_bar.setIconSize(QSize(24, 24))
        context_bar.setFixedHeight(52)

        # 样式：略深的灰色背景 + Arial（跟随全局放大）
        font = QFont("Arial", 13, QFont.Bold)
        context_bar.setFont(font)
        context_bar.setStyleSheet("""
            QToolBar {
                background-color: #dddddd;
                border-top: 1px solid #b0b0b0;
                border-bottom: 1px solid #b0b0b0;
            }
            QLabel {
                color: #000000;
                padding-left: 4px;
                padding-right: 2px;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #808080;
                padding: 1px 4px;
                /* 提高最小高度保证文字不被裁切，同时与工具栏高度匹配 */
                min-height: 30px;
                font: 13pt "Arial";
            }
            /* 禁用时也保持同样字号（有些平台会“看起来更小”） */
            QComboBox:disabled {
                color: #555555;
                background-color: #f2f2f2;
            }
        """)

        def vline():
            line = QFrame()
            line.setFrameShape(QFrame.VLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setLineWidth(1)
            return line

        # Module 选择（从原 Module Toolbar 移入此处）
        lbl_module = QLabel("Module:")
        lbl_module.setFont(font)
        lbl_module.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        lbl_module.setFixedHeight(36)
        context_bar.addWidget(lbl_module)

        self.module_combo = QComboBox()
        self.module_combo.setFont(font)
        self.module_combo.setFixedHeight(36)
        self.module_combo.addItems([
            "Part", "Property", "Assembly", "Step", "Interaction",
            "Load", "Mesh", "Job", "Visualization"
        ])
        self.module_combo.setCurrentText("Part")
        context_bar.addWidget(self.module_combo)

        context_bar.addWidget(vline())

        # Model（静态）
        lbl_model = QLabel("Model:")
        lbl_model.setFont(font)
        lbl_model.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        lbl_model.setFixedHeight(36)
        context_bar.addWidget(lbl_model)

        self.model_combo = QComboBox()
        self.model_combo.setFont(font)
        self.model_combo.setFixedHeight(36)
        self.model_combo.addItem("Model-1")
        self.model_combo.setEnabled(False)
        context_bar.addWidget(self.model_combo)

        context_bar.addWidget(vline())

        # Step（静态）
        lbl_step = QLabel("Step:")
        lbl_step.setFont(font)
        lbl_step.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        lbl_step.setFixedHeight(36)
        context_bar.addWidget(lbl_step)

        self.step_combo = QComboBox()
        self.step_combo.setFont(font)
        self.step_combo.setFixedHeight(36)
        self.step_combo.addItem("Initial")
        self.step_combo.setEnabled(False)
        context_bar.addWidget(self.step_combo)

        self.addToolBar(context_bar)
        
    def create_statusbar(self):
        """创建状态栏"""
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.addWidget(QLabel("Ready"))
        
    def create_dock_widgets(self):
        """创建左侧dock widgets"""
        # 左侧面板配置 - 减小宽度，使界面更紧凑
        LEFT_DOCK_MIN_WIDTH = 130

        # === 模型树 Dock ===
        self.model_tree_dock = QDockWidget("Model Tree", self)
        self.model_tree_dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.model_tree_dock.setMinimumWidth(LEFT_DOCK_MIN_WIDTH)

        # 实例化新的模型树 Widget
        self.model_tree_widget = ModelTreeWidget(self)
        
        # 【关键】连接双击信号到处理函数
        self.model_tree_widget.item_edit_requested.connect(self.on_tree_item_double_clicked)

        self.model_tree_dock.setWidget(self.model_tree_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.model_tree_dock)
        
        # === 工具箱 Dock (使用 QScrollArea 防止窗口缩放时控件重叠) ===
        self.toolbox_dock = QDockWidget("Toolbox", self)
        self.toolbox_dock.setAllowedAreas(Qt.LeftDockWidgetArea)
        self.toolbox_dock.setMinimumWidth(LEFT_DOCK_MIN_WIDTH)
        
        # 创建 ScrollArea 作为容器
        self.toolbox_scroll = QScrollArea()
        self.toolbox_scroll.setWidgetResizable(True)  # 允许内部 widget 调整大小
        self.toolbox_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用横向滚动
        self.toolbox_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 需要时显示纵向滚动
        self.toolbox_scroll.setFrameShape(QFrame.NoFrame)  # 无边框
        
        # 创建内部 widget 和布局
        self.toolbox_widget = QWidget()
        self.toolbox_widget.setMinimumWidth(0)
        self.toolbox_widget.setFont(QFont("Segoe UI", 10))
        
        self.toolbox_layout = QGridLayout(self.toolbox_widget)
        self.toolbox_layout.setContentsMargins(12, 12, 12, 12)  # 增加内边距
        self.toolbox_layout.setHorizontalSpacing(12)  # 增加水平间距
        self.toolbox_layout.setVerticalSpacing(5)  # 紧凑化垂直间距
        
        # 将 widget 放入 ScrollArea
        self.toolbox_scroll.setWidget(self.toolbox_widget)
        
        # 将 ScrollArea 设置为 DockWidget 的内容
        self.toolbox_dock.setWidget(self.toolbox_scroll)
        # 设置 Toolbox 的最小高度
        self.toolbox_dock.setMinimumHeight(120)  # 设置更小的最小高度
        self.addDockWidget(Qt.LeftDockWidgetArea, self.toolbox_dock)
        
        # 使用 QTimer 在窗口显示后设置初始高度
        QTimer.singleShot(100, lambda: self._set_toolbox_height(self.toolbox_dock))

        # 初始化一个空结构，防止启动时空白
        self.model_tree_widget.update_structure({})

    def on_model_tree_item_clicked(self, item, column):
        """模型树点击联动模块切换"""
        text = item.text(0)
        if not text:
            return

        # 顶层分类名
        key = text.split()[0]  # 例如 "Parts", "Loads", "Mesh"

        mapping = {
            "Parts": "Part",
            "Materials": "Property",
            "Sections": "Property",
            "Assembly": "Assembly",
            "Steps": "Step",
            "Interactions": "Interaction",
            "Loads": "Load",
            "Mesh": "Mesh",
            "Jobs": "Job",
        }

        module = mapping.get(key)
        if module and self.module_combo.currentText() != module:
            self.module_combo.setCurrentText(module)
    
    # ---------------- 模型树上下文菜单与双击激活的回调 ----------------
    def on_model_tree_create_requested(self, payload):
        """
        在容器节点下创建对象，例如：
        - 右键 Parts -> Create Part...
        - 右键 Materials -> Create Material...
        """
        category = payload.get("category")
        if category == "parts":
            # 模块自动切到 Part，仿 Abaqus 行为
            self.module_combo.setCurrentText("Part")
            self.create_part()
        elif category == "materials":
            self.module_combo.setCurrentText("Property")
            self.create_material()
        elif category == "steps":
            self.module_combo.setCurrentText("Step")
            self.create_step()
        elif category == "loads":
            self.module_combo.setCurrentText("Load")
            self.create_load()
        elif category == "mesh":
            self.module_combo.setCurrentText("Mesh")
            self.mesh_part()
        elif category == "jobs":
            self.module_combo.setCurrentText("Job")
            self.create_job()
        else:
            # 其它容器目前暂不实现具体逻辑，仅给出提示
            self.message_area.appendPlainText(f"[TODO] Create under container: {category}\n")

    def on_model_tree_edit_requested(self, payload):
        """编辑具体对象节点，例如 Part-1 / 某个 Load 分组等"""
        category = payload.get("category")
        if category == "part":
            self.module_combo.setCurrentText("Part")
            self.edit_part()
        elif category == "material":
            self.module_combo.setCurrentText("Property")
            # 目前没有单独的 edit_material，对应功能后续可细化
            self.create_material()
        else:
            self.message_area.appendPlainText(f"[TODO] Edit object: {payload.get('name', '')} ({category})\n")

    def on_model_tree_rename_requested(self, payload):
        """重命名对象（示例实现：弹个对话框，后续可真正修改 self.model_database 再刷新树）"""
        from PyQt5.QtWidgets import QInputDialog
        old_name = payload.get("name", "")
        ok, new_name = QInputDialog.getText(self, "Rename", "New name:", text=old_name)
        if ok and new_name and new_name != old_name:
            self.message_area.appendPlainText(f"[TODO] Rename {old_name} -> {new_name}\n")
            # 这里按需更新 self.model_database，然后：
            # self.model_tree_widget.update_structure(self.model_database)

    def on_model_tree_delete_requested(self, payload):
        """删除对象节点（这里只做示例提示，真实删除需要操作 self.model_database）"""
        name = payload.get("name", "")
        category = payload.get("category", "")
        reply = QMessageBox.question(
            self,
            "Delete",
            f"Delete {category}: {name} ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.message_area.appendPlainText(f"[TODO] Delete {category}: {name}\n")
            # 按需从 self.model_database 中删除，并刷新：
            # self.model_tree_widget.update_structure(self.model_database)

    def on_model_tree_set_active_requested(self, payload):
        """右键菜单 'Set as Active'"""
        self.on_model_tree_object_activated(payload)

    def on_model_tree_object_activated(self, payload):
        """
        双击 Part / Assembly 节点时：
        - 设置为当前工作对象
        - 清空 3D 视口并绘制对应网格
        - 自动切换顶部 Module 下拉框
        """
        category = payload.get("category")
        obj = payload.get("object")
        name = payload.get("name", "")

        # 标记当前对象
        self.current_object = payload
        self.statusBar.showMessage(f"Active {category}: {name}")

        # 清空视口
        self.plotter.clear()

        # 尝试从对象中提取 PyVista 网格（这里约定常见几种形式，实际可按你的 Part 类调整）
        grid = None
        try:
            if obj is not None:
                # 1）对象本身就是 PyVista 数据集
                if isinstance(obj, pv.DataSet):
                    grid = obj
                # 2）对象有 to_pyvista() 方法
                elif hasattr(obj, "to_pyvista"):
                    grid = obj.to_pyvista()
                # 3）对象携带 nodes / elements 字典，复用现有 FEMVisualizer
                elif isinstance(obj, dict) and "nodes" in obj and "elements" in obj:
                    from utils.visualizer import FEMVisualizer
                    visualizer = FEMVisualizer()
                    grid = visualizer.parse_mesh_to_vtk(obj["nodes"], obj["elements"])
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Failed to build mesh for {name}: {e}")

        if grid is not None:
            self.plotter.add_mesh(grid, show_edges=True, color='lightblue', opacity=0.8)
            self._set_camera_view('iso')
        else:
            # 没有可用网格时，仅在消息区提示
            self.message_area.appendPlainText(f"No mesh data bound for {category}: {name}\n")

        # 自动切换顶部模块
        if category == "part":
            self.module_combo.setCurrentText("Part")
        elif category == "assembly":
            self.module_combo.setCurrentText("Assembly")
        
    def create_central_widget(self):
        """创建中央视口"""
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # PyVista视口 - Abaqus 经典渐变蓝背景
        self.plotter = QtInteractor(central_widget)
        # 底色灰蓝 + 顶色深海军蓝，模拟 Abaqus 渐变蓝
        self.plotter.set_background(color="#acbccc", top="#003366")
        # 显示坐标轴
        self.plotter.add_axes()
        
        layout.addWidget(self.plotter.interactor)
        self.setCentralWidget(central_widget)
        
    def create_bottom_area(self):
        """创建底部消息区域"""
        bottom_dock = QDockWidget("Message Area", self)
        bottom_dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # 消息历史
        self.message_area = QPlainTextEdit()
        self.message_area.setPlainText("A new model database has been created.\n")
        # 设置合理的初始高度，允许用户通过拖拽 DockWidget 调整大小
        self.message_area.setMinimumHeight(60)  # 减小最小高度，初始时更矮
        # 移除固定高度限制，允许自由调整
        bottom_layout.addWidget(self.message_area)
        
        # 命令行已移除 - 不再需要命令输入功能
        
        bottom_dock.setWidget(bottom_widget)
        # 设置 DockWidget 的最小高度
        bottom_dock.setMinimumHeight(80)  # 减小 DockWidget 的最小高度，初始时更矮
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom_dock)
        self.bottom_dock = bottom_dock  # 保存引用以便后续设置初始大小
        
        # 保存引用以便后续设置大小
        self.message_area_dock = bottom_dock
        
    def _set_initial_dock_sizes(self):
        """设置 DockWidget 的初始大小，使其初始时更矮"""
        # 使用 resizeDocks 方法设置底部 Message Area 的初始高度
        if hasattr(self, 'bottom_dock') and self.bottom_dock:
            # 设置底部 Message Area 的初始高度为 80px
            self.resizeDocks([self.bottom_dock], [140], Qt.Vertical)
        
        # 对于左侧的 Toolbox，由于是水平方向的 DockWidget，高度由内容决定
        # 我们已经设置了最小高度为 150px，这会在初始时生效
        # 如果需要更精确的控制，可以通过设置内部 widget 的固定高度
        # 但考虑到有 ScrollArea，让内容自然决定高度更合适
        
    def on_module_changed(self):
        """模块切换时更新工具箱"""
        module = self.module_combo.currentText()

        # Toolbox 字体统一控制：按钮/标签/下拉框等用略小于全局的字号
        toolbox_font = QFont("Arial", 11)
        toolbox_font_bold = QFont("Arial", 11, QFont.Bold)
        
        # 清除现有按钮
        for i in reversed(range(self.toolbox_layout.count())):
            widget = self.toolbox_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        # 清空旧的 row stretch，避免切换模块后残留影响布局
        self.toolbox_layout.setRowStretch(0, 0)
        self.toolbox_layout.setRowStretch(1, 0)
        self.toolbox_layout.setRowStretch(2, 0)
        self.toolbox_layout.setRowStretch(3, 0)
        self.toolbox_layout.setRowStretch(4, 0)
        self.toolbox_layout.setRowStretch(5, 0)
        self.toolbox_layout.setRowStretch(6, 0)
        self.toolbox_layout.setRowStretch(7, 0)
        self.toolbox_layout.setRowStretch(8, 0)
        self.toolbox_layout.setRowStretch(9, 0)
        
        # 根据模块添加按钮和连接
        if module == "Part":
            buttons = [
                ("Create Part", self.create_part),
                ("Extrude", self.extrude_shape),
                ("Revolve", self.revolve_shape),
                ("Cut", self.cut_part),
                ("Fillet", self.create_fillet),
                ("Chamfer", self.create_chamfer)
            ]
            start_row = 0
        elif module == "Property":
            buttons = [
                ("Create Material", self.create_material),
                ("Create Section", self.create_section),
                ("Assign Property", self.assign_property)
            ]
            start_row = 0
        elif module == "Assembly":
            buttons = [
                ("Create Instance", self.create_instance),
                ("Translate", self.translate_instance),
                ("Rotate", self.rotate_instance)
            ]
            start_row = 0
        elif module == "Step":
            buttons = [
                ("Create Step", self.create_step),
                ("Edit Step", self.edit_step)
            ]
            start_row = 0
        elif module == "Interaction":
            buttons = [
                ("Create Contact", self.create_contact),
                ("Create Constraint", self.create_constraint)
            ]
            start_row = 0
        elif module == "Load":
            buttons = [
                ("Create Load", self.create_load),
                ("Create BC", self.create_boundary_condition)
            ]
            start_row = 0
        elif module == "Mesh":
            buttons = [
                ("Seed Edges", self.seed_edges),
                ("Mesh Part", self.mesh_part),
                ("Verify Mesh", self.verify_mesh)
            ]
            start_row = 0
        elif module == "Job":
            buttons = [
                ("Create Job", self.create_job),
                ("Submit Job", self.submit_job),
                ("Monitor Job", self.monitor_job)
            ]
            start_row = 0
        elif module == "Visualization":
            # 添加结果类型选择器
            self.result_combo = QComboBox()
            self.result_combo.setFont(toolbox_font)
            self.result_combo.addItems([
                "VonMises", "Displacement", "S11 (σx)", "S22 (σy)", "S33 (σz)", 
                "S12 (τxy)", "S23 (τyz)", "S13 (τxz)"
            ])
            self.result_combo.currentTextChanged.connect(self.on_result_type_changed)
            
            # 颜色映射选择器
            from utils.visualizer import FEMVisualizer
            self.cmap_combo = QComboBox()
            self.cmap_combo.setFont(toolbox_font)
            self.cmap_combo.addItems(FEMVisualizer.AVAILABLE_CMAPS)
            self.cmap_combo.setCurrentText("jet")
            self.cmap_combo.currentTextChanged.connect(self.on_cmap_changed)
            
            # 范围控制
            self.auto_range_check = QCheckBox("Auto Range")
            self.auto_range_check.setFont(toolbox_font)
            self.auto_range_check.setChecked(True)
            self.auto_range_check.toggled.connect(self.on_auto_range_toggled)
            
            self.range_min_edit = QDoubleSpinBox()
            self.range_min_edit.setFont(toolbox_font)
            self.range_min_edit.setMinimum(-1e10)
            self.range_min_edit.setMaximum(1e10)
            self.range_min_edit.setDecimals(3)
            self.range_min_edit.setPrefix("Min: ")
            self.range_min_edit.setEnabled(False)
            
            self.range_max_edit = QDoubleSpinBox()
            self.range_max_edit.setFont(toolbox_font)
            self.range_max_edit.setMinimum(-1e10)
            self.range_max_edit.setMaximum(1e10)
            self.range_max_edit.setDecimals(3)
            self.range_max_edit.setPrefix("Max: ")
            self.range_max_edit.setEnabled(False)
            
            self.apply_range_btn = QPushButton("Apply Range")
            self.apply_range_btn.setFont(toolbox_font_bold)
            self.apply_range_btn.setEnabled(False)
            self.apply_range_btn.clicked.connect(self.on_apply_range)
            
            buttons = [
                # 使用当前选择的"内部字段名"进行绘图，而不是界面显示文本
                ("Plot Contours", lambda: self.plot_results(
                    self.result_type_map.get(self.result_combo.currentText(), "VonMises")
                )),
                ("Plot Vectors", self.plot_vectors),
                ("Animate", self.animate_results)
            ]
            
            # 特殊处理Visualization模块：添加选择器
            row = 0
            lbl_rt = QLabel("Result Type:")
            lbl_rt.setFont(toolbox_font)
            self.toolbox_layout.addWidget(lbl_rt, row, 0)
            self.toolbox_layout.addWidget(self.result_combo, row, 1)
            row += 1
            
            lbl_cm = QLabel("Colormap:")
            lbl_cm.setFont(toolbox_font)
            self.toolbox_layout.addWidget(lbl_cm, row, 0)
            self.toolbox_layout.addWidget(self.cmap_combo, row, 1)
            row += 1
            
            self.toolbox_layout.addWidget(self.auto_range_check, row, 0, 1, 2)
            row += 1
            
            self.toolbox_layout.addWidget(self.range_min_edit, row, 0, 1, 2)
            row += 1
            
            self.toolbox_layout.addWidget(self.range_max_edit, row, 0, 1, 2)
            row += 1
            
            self.toolbox_layout.addWidget(self.apply_range_btn, row, 0, 1, 2)
            row += 1
            
            # 添加 BC 和 Load 显示复选框
            self.show_bc_loads_check = QCheckBox("Show BCs & Loads")
            self.show_bc_loads_check.setFont(toolbox_font)
            self.show_bc_loads_check.setChecked(self.show_bc_loads)
            self.show_bc_loads_check.toggled.connect(self.on_show_bc_loads_toggled)
            self.toolbox_layout.addWidget(self.show_bc_loads_check, row, 0, 1, 2)
            row += 1
            
            # 从下一行开始添加按钮
            start_row = row
        else:
            buttons = []
            start_row = 0
        
        # Toolbox：模块功能按钮（无图标，竖直一列排列）
        cols = 1
        for i, (btn_text, callback) in enumerate(buttons):
            btn = QPushButton(btn_text)
            btn.setFont(toolbox_font_bold)  # 使用缩小前的按钮字号
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumWidth(0)
            btn.setFixedHeight(30)  # 减小按钮高度，使布局更紧凑
            btn.clicked.connect(callback)

            # 每个按钮占一行，排成一列
            row = i + start_row
            col = 0
            self.toolbox_layout.addWidget(btn, row, col)

        # 关键：把实际用到的每一行设置 stretch，让竖向空间按行均匀分配，
        # 避免所有按钮堆在上面、下面空一大块。
        if buttons:
            # 竖直多行时，对所有按钮所在的行设置 stretch，让竖向空间均匀分配
            last_row = ((len(buttons) - 1) // cols) + start_row
            for r in range(start_row, last_row + 1):
                self.toolbox_layout.setRowStretch(r, 1)
        
        # 调整dock标题
        self.toolbox_dock.setWindowTitle(f"{module} Toolbox")
        
    def on_result_type_changed(self, result_type):
        """结果类型改变时自动更新显示"""
        # 将下拉框显示文本映射为网格中的真实字段名
        internal_name = self.result_type_map.get(result_type, "VonMises")
        if hasattr(self, 'current_mesh') and self.current_mesh and self.current_disp is not None:
            self.plot_results(internal_name)
    
    def on_cmap_changed(self, cmap_name):
        """颜色映射改变时的回调"""
        if hasattr(self, 'current_mesh') and self.current_mesh and self.current_disp is not None:
            result_type = self.result_type_map.get(self.result_combo.currentText(), "VonMises")
            self.plot_results(result_type)
    
    def on_auto_range_toggled(self, checked):
        """自动范围切换时的回调"""
        self.range_min_edit.setEnabled(not checked)
        self.range_max_edit.setEnabled(not checked)
        self.apply_range_btn.setEnabled(not checked)
        if checked and hasattr(self, 'current_mesh') and self.current_mesh and self.current_disp is not None:
            # 自动更新范围
            result_type = self.result_type_map.get(self.result_combo.currentText(), "VonMises")
            self._update_range_from_data(result_type)
            self.plot_results(result_type)
    
    def on_apply_range(self):
        """应用自定义范围"""
        if hasattr(self, 'current_mesh') and self.current_mesh and self.current_disp is not None:
            result_type = self.result_type_map.get(self.result_combo.currentText(), "VonMises")
            self.plot_results(result_type)
    
    def on_show_bc_loads_toggled(self, checked):
        """BC 和 Load 显示复选框切换时的回调"""
        self.show_bc_loads = checked
        if checked:
            # 如果启用，添加 BC 和 Load actors
            if self.inp_data:
                self._add_bc_load_actors()
        else:
            # 如果禁用，移除 BC 和 Load actors
            self._clear_bc_load_actors()
    
    def _add_bc_load_actors(self):
        """添加 BC 和 Load 可视化 actors"""
        if not self.inp_data:
            return
        
        try:
            from utils.visualizer import FEMVisualizer
            visualizer = FEMVisualizer()
            
            # 获取节点数据（可能是字典或对象）
            nodes_map = None
            if self.current_mesh and 'nodes' in self.current_mesh:
                nodes_map = self.current_mesh['nodes']
            elif 'nodes' in self.inp_data:
                nodes_map = self.inp_data['nodes']
            
            if nodes_map is None:
                return
            
            # 创建 BC actors
            bc_actors = visualizer.create_bc_actors(self.inp_data, nodes_map)
            for actor_data in bc_actors:
                actor = self.plotter.add_mesh(
                    actor_data['mesh'],
                    color=actor_data['color'],
                    show_edges=False
                )
                self.bc_load_actors.append(actor)
            
            # 创建 Load actors
            load_actors = visualizer.create_load_actors(self.inp_data, nodes_map)
            for actor_data in load_actors:
                actor = self.plotter.add_mesh(
                    actor_data['mesh'],
                    color=actor_data['color'],
                    show_edges=False
                )
                self.bc_load_actors.append(actor)
            
        except Exception as e:
            self.message_area.appendPlainText(f"Warning: Failed to add BC/Load visualization: {str(e)}\n")
    
    def _clear_bc_load_actors(self):
        """清除 BC 和 Load 可视化 actors"""
        for actor in self.bc_load_actors:
            try:
                self.plotter.remove_actor(actor)
            except Exception:
                pass  # Actor may have already been removed
        self.bc_load_actors.clear()
    
    def _update_range_from_data(self, result_type):
        """从数据中更新范围显示"""
        try:
            from utils.visualizer import FEMVisualizer
            visualizer = FEMVisualizer()
            grid = visualizer.parse_mesh_to_vtk(
                self.current_mesh['nodes'], 
                self.current_mesh['elements'], 
                displacement=self.current_disp,
                stress=self.current_stress,
                stress_components=self.current_stress_components
            )
            
            if result_type == "Displacement":
                disp_magnitude = np.linalg.norm(grid.point_data['Displacement'], axis=1)
                min_val, max_val = float(np.min(disp_magnitude)), float(np.max(disp_magnitude))
            else:
                min_val, max_val = visualizer.get_scalar_range(grid, result_type)
            
            if min_val is not None and max_val is not None:
                self.range_min_edit.setValue(min_val)
                self.range_max_edit.setValue(max_val)
        except Exception as e:
            pass  # 静默失败
        
    # 其他方法保持简化为避免阻塞
    def new_model_database(self):
        """新建模型数据库"""
        self.message_area.appendPlainText("A new model database has been created.\n")
        self.statusBar.showMessage("New model database created")
        
    def open_file(self):
        """打开文件"""
        from PyQt5.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(self, "Open INP File", "", "INP files (*.inp);;All files (*)")
        if filename:
            self.load_inp_file(filename)
            
    def save_file(self):
        """保存文件"""
        QMessageBox.information(self, "Save", "保存功能暂时还没有完善")
        
    def import_file(self):
        """导入文件"""
        QMessageBox.information(self, "Import", "导入功能暂时还没有完善")
        
    def export_file(self):
        """导出文件"""
        QMessageBox.information(self, "Export", "导出功能暂时还没有完善")
        
    def load_inp_file(self, filename):
        """加载INP文件"""
        try:
            from utils.inp_reader import InpParser
            parser = InpParser()
            self.inp_data = parser.read(filename)
            
            self.message_area.appendPlainText(f"Successfully loaded: {filename}\n")
            self.statusBar.showMessage(f"Loaded {filename}")
            
            # === 【关键】更新左侧模型树结构 ===
            self.model_tree_widget.update_structure(self.inp_data)
            
            # 自动切换到 Visualization 模块显示网格
            self.module_combo.setCurrentText("Visualization")
            self.plot_mesh()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def on_tree_item_double_clicked(self, payload):
        """
        处理模型树双击事件：弹出数据表格
        """
        category = payload.get("category")
        name = payload.get("name")
        
        # 确保有数据已加载
        if not hasattr(self, 'inp_data') or not self.inp_data:
            return

        headers = []
        table_data = []
        dialog_title = ""

        # === 情况 1: 查看 Elements (单元数据) ===
        if category == "mesh" and name == "Elements":
            dialog_title = "Element Data"
            # 获取所有单元数据 {eid: [n1, n2, ...]}
            elements = self.inp_data.get('elements', {})
            if not elements:
                self.message_area.appendPlainText("No elements data found.\n")
                return

            # 动态生成表头: [Element ID, Node 1, Node 2, ...]
            # 假设所有单元节点数相同，取第一个来看看
            first_eid = next(iter(elements))
            num_nodes = len(elements[first_eid])
            headers = ["Element"] + [f"Node {i+1}" for i in range(num_nodes)]
            
            # 准备数据
            for eid, nodes in elements.items():
                row = [eid] + nodes
                table_data.append(row)

        # === 情况 2: 查看 Nodes (节点数据) ===
        elif category == "mesh" and name == "Nodes":
            dialog_title = "Node Data"
            nodes = self.inp_data.get('nodes', {})
            if not nodes:
                self.message_area.appendPlainText("No nodes data found.\n")
                return
                
            headers = ["Node Label", "X", "Y", "Z"]
            for nid, coords in nodes.items():
                row = [nid] + coords # coords 是 [x, y, z] 列表
                table_data.append(row)
                
        # === 情况 3: 查看 Nset (节点集合) ===
        elif category == "nset":
            dialog_title = f"Nset: {name}"
            ids = payload.get("ids", [])
            headers = ["Node Label"]
            for nid in ids:
                table_data.append([nid])
                
        # === 情况 4: 查看 Eset (单元集合) ===
        elif category == "elset":
            dialog_title = f"Elset: {name}"
            ids = payload.get("ids", [])
            headers = ["Element Label"]
            for eid in ids:
                table_data.append([eid])

        # 如果准备好了数据，就弹出窗口
        if table_data:
            dialog = DataViewerDialog(dialog_title, headers, table_data, self)
            dialog.exec_()
        else:
            # 如果点的不是上面几种，或者没数据，就不弹窗
            pass
            
    def plot_mesh(self):
        """绘制网格"""
        if not self.inp_data or 'nodes' not in self.inp_data or 'elements' not in self.inp_data:
            QMessageBox.warning(self, "Warning", "No mesh data available")
            return

        try:
            from utils.visualizer import FEMVisualizer
            visualizer = FEMVisualizer()
            grid = visualizer.parse_mesh_to_vtk(self.inp_data['nodes'], self.inp_data['elements'])

            # —— 关键：在仅有网格时也初始化 current_mesh，使视图按钮可用 ——
            # 之前 only 在 on_solver_finished 里设置 current_mesh，
            # 导致导入 INP 但未求解时，视图菜单判断 `self.current_mesh` 为 False，按钮不起作用。
            self.current_mesh = {
                'nodes': self.inp_data['nodes'],
                'elements': self.inp_data['elements']
            }
            # 尚无位移与应力结果，显式清空
            self.current_disp = None
            self.current_stress = None
            self.current_stress_components = None

            # 清除现有网格和 BC/Load actors
            self.plotter.clear()
            self._clear_bc_load_actors()
            # 添加新网格
            self.plotter.add_mesh(grid, show_edges=True, color='lightblue', opacity=0.8)
            # 如果启用了 BC 和 Load 显示，添加它们
            if self.show_bc_loads and self.inp_data:
                self._add_bc_load_actors()
            self._set_camera_view('top')  # 设置为顶视图，正视x-y平面
            self.message_area.appendPlainText("Mesh displayed successfully\n")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot mesh: {str(e)}")
            
    def run_solver(self, solver_settings=None):
        """启动后台求解线程"""
        if not self.inp_data: 
            return
        
        # 如果未传入配置（例如从其他入口调用），使用默认线性配置
        if solver_settings is None:
            solver_settings = {"type": "Linear"}

        # 如果已有worker在运行，先停止它
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            if not self.worker.wait(1000):  # 等待1秒
                self.worker.terminate()
                self.worker.wait()
            self.worker = None
        
        # 清空历史监控数据，开始新的求解
        self.monitor_data = {
            'log_messages': [],
            'iterations': [],
            'residuals': [],
            'status_history': [],
            'progress': 0,
            'is_completed': False
        }

        try:
            from gui.worker import SolverWorker
            
            # 实例化 Worker，传入配置参数
            self.worker = SolverWorker(
                "", # path 为空，因为我们传入 inp_data_override
                inp_data=self.inp_data, 
                material_props=self.material_props,
                solver_config=solver_settings # <--- 关键：传递配置
            )
            
            # 连接信号（同时保存到监控历史数据）
            self.worker.log_signal.connect(self.message_area.appendPlainText)
            self.worker.log_signal.connect(self._on_monitor_log)  # 保存日志到历史
            self.worker.progress_signal.connect(lambda val: self.statusBar.showMessage(f"Progress: {val}%"))
            self.worker.progress_signal.connect(self._on_monitor_progress)  # 保存进度到历史
            self.worker.monitor_signal.connect(self._on_monitor_status)  # 保存状态到历史
            self.worker.finished_signal.connect(self.on_solver_finished)
            self.worker.finished_signal.connect(self._on_monitor_finished)  # 标记完成
            self.worker.error_signal.connect(lambda msg: QMessageBox.critical(self, "Solver Error", msg))
            self.worker.error_signal.connect(lambda msg: self._on_monitor_log(f"ERROR: {msg}"))  # 保存错误到历史
            
            # 如果监控窗口已打开，也连接到监控窗口进行实时显示
            if self.monitor_dialog is not None:
                self.worker.log_signal.connect(self.monitor_dialog.append_log)
                self.worker.progress_signal.connect(self.monitor_dialog.update_progress)
                self.worker.monitor_signal.connect(self.monitor_dialog.update_status)
            
            # 启动
            self.worker.start()
            
            type_str = solver_settings.get('type', 'Linear')
            self.statusBar.showMessage(f"Running Analysis ({type_str})...")
            
            # 如果监控窗口已打开，确保信号已连接
            if self.monitor_dialog is not None:
                # 重新连接信号（防止之前的连接已断开）
                try:
                    self.worker.log_signal.connect(self.monitor_dialog.append_log)
                    self.worker.progress_signal.connect(self.monitor_dialog.update_progress)
                    self.worker.monitor_signal.connect(self.monitor_dialog.update_status)
                    self.worker.finished_signal.connect(self._on_monitor_finished)
                except Exception:
                    pass  # 如果已连接，忽略错误
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start solver: {str(e)}")
            
    def on_solver_finished(self, nodes, elements, displacement, stress, stress_components):
        """求解完成回调"""
        self.current_mesh = {'nodes': nodes, 'elements': elements}
        self.current_disp = displacement
        self.current_stress = stress
        self.current_stress_components = stress_components  # 保存应力分量
        
        # 自动切换到Visualization模块
        self.module_combo.setCurrentText("Visualization")
        self.plot_results()
        self.message_area.appendPlainText("Analysis completed successfully\n")
        self.statusBar.showMessage("Analysis completed")
        
    def plot_results(self, result_type="VonMises"):
        """绘制结果
        
        Args:
            result_type: "Displacement", "VonMises", "S11", "S22", "S33", "S12", "S23", "S13"
        """
        if not self.current_mesh or self.current_disp is None:
            QMessageBox.warning(self, "Warning", "No results available")
            return
            
        try:
            from utils.visualizer import FEMVisualizer
            visualizer = FEMVisualizer()
            grid = visualizer.parse_mesh_to_vtk(
                self.current_mesh['nodes'], 
                self.current_mesh['elements'], 
                displacement=self.current_disp,
                stress=self.current_stress,
                stress_components=self.current_stress_components
            )
            
            # 获取颜色映射和范围设置
            cmap_name = "jet"  # 默认值
            scalar_range = None  # 默认自动范围
            
            if hasattr(self, 'cmap_combo'):
                cmap_name = visualizer.validate_cmap(self.cmap_combo.currentText())
            
            if hasattr(self, 'auto_range_check'):
                if not self.auto_range_check.isChecked():
                    min_val = self.range_min_edit.value()
                    max_val = self.range_max_edit.value()
                    scalar_range = [min_val, max_val]
                else:
                    # 更新范围显示
                    self._update_range_from_data(result_type)
            
            # 清除现有网格和标尺
            self.plotter.clear()
            self.plotter.scalar_bars.clear()
            self._clear_bc_load_actors()
            
            if result_type == "Displacement":
                # 显示位移大小
                disp_magnitude = np.linalg.norm(grid.point_data['Displacement'], axis=1)
                warped = grid.warp_by_vector('Displacement', factor=1.0)  # 使用 1.0 避免大变形分析时变形过大
                self.plotter.add_mesh(
                    warped, 
                    scalars=disp_magnitude, 
                    cmap=cmap_name,
                    clim=scalar_range,
                    show_edges=True, 
                    scalar_bar_args={'title': 'Displacement Magnitude'}
                )
                title = 'Displacement Magnitude'
            else:
                # 显示标量场
                warped = grid.warp_by_vector('Displacement', factor=1.0)  # 使用 1.0 避免大变形分析时变形过大
                self.plotter.add_mesh(
                    warped, 
                    scalars=result_type, 
                    cmap=cmap_name,
                    clim=scalar_range,
                    show_edges=True, 
                    scalar_bar_args={'title': f'{result_type}'}
                )
                title = result_type

            # 如果启用了 BC 和 Load 显示，添加它们
            if self.show_bc_loads and self.inp_data:
                self._add_bc_load_actors()
            
            # 不再在切换结果类型时强制重置视角，
            # 保持用户当前的相机角度，提升交互体验。
            self.message_area.appendPlainText(f"Results displayed: {title}\n")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to plot results: {str(e)}")
    
    def reset_view(self):
        QTimer.singleShot(0, self.plotter.reset_camera)
        
    def fit_view(self):
        QTimer.singleShot(0, self.plotter.reset_camera)
        
    def view_front(self):
        """前视图"""
        if hasattr(self, 'current_mesh') and self.current_mesh:
            self._set_camera_view('front')
        
    def view_back(self):
        """后视图"""
        if hasattr(self, 'current_mesh') and self.current_mesh:
            self._set_camera_view('back')
        
    def view_left(self):
        """左视图"""
        if hasattr(self, 'current_mesh') and self.current_mesh:
            self._set_camera_view('left')
        
    def view_right(self):
        """右视图"""
        if hasattr(self, 'current_mesh') and self.current_mesh:
            self._set_camera_view('right')
        
    def view_top(self):
        """顶视图"""
        if hasattr(self, 'current_mesh') and self.current_mesh:
            self._set_camera_view('top')
        
    def view_bottom(self):
        """底视图"""
        if hasattr(self, 'current_mesh') and self.current_mesh:
            self._set_camera_view('bottom')
        
    def view_iso(self):
        """等轴视图"""
        if hasattr(self, 'current_mesh') and self.current_mesh:
            self._set_camera_view('iso')
        
    def _set_camera_view(self, view_type):
        """设置相机视图"""
        import numpy as np
        focal_point = self.plotter.camera.focal_point
        current_pos = self.plotter.camera.position
        distance = np.linalg.norm(np.array(current_pos) - np.array(focal_point))
        
        if view_type == 'top':
            new_pos = (focal_point[0], focal_point[1], focal_point[2] + distance)
            self.plotter.camera.position = new_pos
            self.plotter.camera.up = (0, 1, 0)
        elif view_type == 'bottom':
            new_pos = (focal_point[0], focal_point[1], focal_point[2] - distance)
            self.plotter.camera.position = new_pos
            self.plotter.camera.up = (0, -1, 0)
        elif view_type == 'front':
            new_pos = (focal_point[0], focal_point[1] - distance, focal_point[2])
            self.plotter.camera.position = new_pos
            self.plotter.camera.up = (0, 0, 1)
        elif view_type == 'back':
            new_pos = (focal_point[0], focal_point[1] + distance, focal_point[2])
            self.plotter.camera.position = new_pos
            self.plotter.camera.up = (0, 0, 1)
        elif view_type == 'left':
            new_pos = (focal_point[0] - distance, focal_point[1], focal_point[2])
            self.plotter.camera.position = new_pos
            self.plotter.camera.up = (0, 0, 1)
        elif view_type == 'right':
            new_pos = (focal_point[0] + distance, focal_point[1], focal_point[2])
            self.plotter.camera.position = new_pos
            self.plotter.camera.up = (0, 0, 1)
        elif view_type == 'iso':
            new_pos = (focal_point[0] + distance, focal_point[1] + distance, focal_point[2] + distance)
            self.plotter.camera.position = new_pos
            self.plotter.camera.up = (0, 0, 1)
        self.plotter.interactor.Render()  # 强制刷新视图
        
    # 模型管理方法
    def create_model(self):
        QMessageBox.information(self, "Create Model", "创建模型功能暂时还没有完善")
        
    def copy_model(self):
        QMessageBox.information(self, "Copy Model", "复制模型功能暂时还没有完善")
        
    def rename_model(self):
        QMessageBox.information(self, "Rename Model", "重命名模型功能暂时还没有完善")
        
    def delete_model(self):
        QMessageBox.information(self, "Delete Model", "删除模型功能暂时还没有完善")
        
    # 视口管理方法
    def create_viewport(self):
        QMessageBox.information(self, "Create Viewport", "创建视口功能暂时还没有完善")
        
    def delete_viewport(self):
        QMessageBox.information(self, "Delete Viewport", "删除视口功能暂时还没有完善")
        
    def tile_viewports(self):
        QMessageBox.information(self, "Tile Viewports", "平铺视口功能暂时还没有完善")
        
    # 零件管理方法
    def create_part(self):
        QMessageBox.information(self, "Create Part", "创建零件功能暂时还没有完善")
        
    def edit_part(self):
        QMessageBox.information(self, "Edit Part", "编辑零件功能暂时还没有完善")
        
    # 形状操作方法
    def extrude_shape(self):
        QMessageBox.information(self, "Extrude", "拉伸功能暂时还没有完善")
        
    def revolve_shape(self):
        QMessageBox.information(self, "Revolve", "旋转功能暂时还没有完善")
        
    def cut_part(self):
        QMessageBox.information(self, "Cut", "切割功能暂时还没有完善")
        
    # 特征操作方法
    def create_fillet(self):
        QMessageBox.information(self, "Fillet", "圆角功能暂时还没有完善")
        
    def create_chamfer(self):
        QMessageBox.information(self, "Chamfer", "倒角功能暂时还没有完善")
        
    # 属性管理方法
    def create_material(self):
        """创建/编辑材料属性"""
        from gui.dialogs import MaterialPropertiesDialog
        
        dialog = MaterialPropertiesDialog(self.material_props, self)
        
        if dialog.exec_() == QDialog.Accepted:
            # 获取用户设置的属性
            self.material_props = dialog.get_properties()
            
            # 如果已加载 INP 数据，同步更新第一个材料的属性
            if self.inp_data and self.inp_data.get('materials'):
                mat_name = next(iter(self.inp_data['materials'].keys()))
                self.inp_data['materials'][mat_name]['E'] = self.material_props.get('E')
                self.inp_data['materials'][mat_name]['nu'] = self.material_props.get('nu')
                
                # 同步塑性参数
                if 'plastic' in self.material_props:
                    self.inp_data['materials'][mat_name]['plastic'] = self.material_props['plastic']
                elif 'plastic' in self.inp_data['materials'][mat_name]:
                    # 用户禁用了塑性，移除
                    del self.inp_data['materials'][mat_name]['plastic']
            
            # 日志输出
            props_str = f"E={self.material_props['E']}, ν={self.material_props['nu']}"
            if 'plastic' in self.material_props:
                props_str += f", σy={self.material_props['plastic']['yield_stress']}"
            self.message_area.appendPlainText(f"Material properties updated: {props_str}\n")
        
    def create_section(self):
        QMessageBox.information(self, "Create Section", "创建截面功能暂时还没有完善")
        
    def assign_property(self):
        QMessageBox.information(self, "Assign Property", "分配属性功能暂时还没有完善")
        
    # 装配方法
    def create_instance(self):
        QMessageBox.information(self, "Create Instance", "创建实例功能暂时还没有完善")
        
    def translate_instance(self):
        QMessageBox.information(self, "Translate", "平移功能暂时还没有完善")
        
    def rotate_instance(self):
        QMessageBox.information(self, "Rotate", "旋转功能暂时还没有完善")
        
    # 步骤管理方法
    def create_step(self):
        QMessageBox.information(self, "Create Step", "创建步骤功能暂时还没有完善")
        
    def edit_step(self):
        QMessageBox.information(self, "Edit Step", "编辑步骤功能暂时还没有完善")
        
    # 相互作用方法
    def create_contact(self):
        QMessageBox.information(self, "Create Contact", "创建接触功能暂时还没有完善")
        
    def create_constraint(self):
        QMessageBox.information(self, "Create Constraint", "创建约束功能暂时还没有完善")
        
    # 载荷和边界条件方法
    def create_load(self):
        QMessageBox.information(self, "Create Load", "创建载荷功能暂时还没有完善")
        
    def create_boundary_condition(self):
        QMessageBox.information(self, "Create BC", "创建边界条件功能暂时还没有完善")
        
    # 网格方法
    def seed_edges(self):
        QMessageBox.information(self, "Seed Edges", "种子边功能暂时还没有完善")
        
    def mesh_part(self):
        QMessageBox.information(self, "Mesh Part", "网格划分功能暂时还没有完善")
        
    def verify_mesh(self):
        QMessageBox.information(self, "Verify Mesh", "验证网格功能暂时还没有完善")
        
    # 作业管理方法
    def create_job(self):
        """创建作业 (点击 Job 工具栏按钮时触发)"""
        if not self.inp_data:
            QMessageBox.warning(self, "Warning", "Please load an INP file first")
            return
        
        # 弹出求解器配置对话框
        dialog = SolverSettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # 获取用户配置 (Linear/TL/UL, TimeStep, Tol...)
            settings = dialog.get_settings()
            # 运行求解器
            self.run_solver(settings)
        
    def submit_job(self):
        self.create_job()
        
    def monitor_job(self):
        """打开作业监控窗口（支持查看已完成作业的历史记录）"""
        # 如果监控窗口已打开，则激活它
        if self.monitor_dialog is not None:
            self.monitor_dialog.raise_()
            self.monitor_dialog.activateWindow()
            return
        
        # 创建新的监控窗口
        from gui.monitor import JobMonitorDialog
        job_name = "Job-1"  # 可以从配置中获取
        self.monitor_dialog = JobMonitorDialog(self, job_name)
        
        # 如果有历史数据（已完成或进行中），先恢复显示
        has_history = (self.monitor_data.get('is_completed', False) or 
                      len(self.monitor_data.get('log_messages', [])) > 0 or
                      len(self.monitor_data.get('iterations', [])) > 0)
        
        if has_history:
            self.monitor_dialog.restore_from_history(self.monitor_data)
        
        # 如果 worker 正在运行，连接实时信号到监控窗口
        if self.worker is not None and self.worker.isRunning():
            # 连接实时显示信号（注意：历史数据保存已在 run_solver 中连接）
            self.worker.log_signal.connect(self.monitor_dialog.append_log)
            self.worker.progress_signal.connect(self.monitor_dialog.update_progress)
            self.worker.monitor_signal.connect(self.monitor_dialog.update_status)
        else:
            # 如果没有正在运行的作业，标记为已完成状态
            if self.monitor_data.get('is_completed', False):
                self.monitor_dialog.set_completed()
            elif has_history:
                # 有历史数据但未标记为完成，可能是被中断的
                self.monitor_dialog.lbl_status.setText("Status: Viewing History")
                self.monitor_dialog.btn_stop.setEnabled(False)
                self.monitor_dialog.btn_stop.setText("No Active Job")
        
        # 窗口关闭时清理引用
        self.monitor_dialog.finished.connect(self._on_monitor_closed)
        
        # 显示窗口（非模态，允许用户继续操作主窗口）
        self.monitor_dialog.show()
    
    def _on_monitor_log(self, msg):
        """监控日志回调，同时保存到历史数据"""
        # 保存到历史数据（无论监控窗口是否打开）
        self.monitor_data['log_messages'].append(msg)
        # 如果监控窗口已打开，实时显示
        if self.monitor_dialog:
            self.monitor_dialog.append_log(msg)
    
    def _on_monitor_progress(self, val):
        """监控进度回调，同时保存到历史数据"""
        if self.monitor_dialog:
            self.monitor_dialog.update_progress(val)
        # 保存到历史数据
        self.monitor_data['progress'] = val
    
    def _on_monitor_status(self, data):
        """监控状态回调，同时保存到历史数据"""
        if self.monitor_dialog:
            self.monitor_dialog.update_status(data)
        # 保存到历史数据
        self.monitor_data['status_history'].append(data.copy())
        # 保存残差和迭代数据（用于绘制收敛曲线）
        if 'residual' in data:
            residual = data['residual']
            self.monitor_data['residuals'].append(residual)
            # 迭代次数从1开始递增
            self.monitor_data['iterations'].append(len(self.monitor_data['residuals']))
    
    def _on_monitor_closed(self):
        """监控窗口关闭时的清理"""
        if self.monitor_dialog:
            # 断开信号连接
            if self.worker:
                try:
                    self.worker.log_signal.disconnect(self.monitor_dialog.append_log)
                    self.worker.progress_signal.disconnect(self.monitor_dialog.update_progress)
                    self.worker.monitor_signal.disconnect(self.monitor_dialog.update_status)
                    self.worker.finished_signal.disconnect(self._on_monitor_finished)
                except Exception:
                    pass  # 如果已经断开，忽略错误
            self.monitor_dialog = None
    
    def _on_monitor_finished(self, *args):
        """求解完成时更新监控窗口"""
        self.monitor_data['is_completed'] = True
        self.monitor_data['progress'] = 100
        if self.monitor_dialog:
            self.monitor_dialog.update_progress(100)
            self.monitor_dialog.append_log("\n*** Analysis Completed Successfully ***\n")
            self.monitor_dialog.set_completed()
    
    def stop_solver(self):
        """停止求解器（由监控窗口调用）"""
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.message_area.appendPlainText("\n*** Job termination requested by user ***\n")
        
    # 可视化方法
    def plot_contours(self):
        """绘制云图"""
        if self.current_stress is None or len(self.current_stress) == 0:
            QMessageBox.warning(self, "Warning", "No stress results available. Please run analysis first.")
            return
        self.plot_results()
        
    def plot_vectors(self):
        """绘制矢量图"""
        QMessageBox.information(self, "Plot Vectors", "绘制矢量图功能暂时还没有完善")
        
    def animate_results(self):
        """动画结果"""
        QMessageBox.information(self, "Animate", "动画功能暂时还没有完善")
        
    # 工具方法
    def query_tool(self):
        QMessageBox.information(self, "Query", "查询工具暂时还没有完善")
        
    def measure_tool(self):
        QMessageBox.information(self, "Measure", "测量工具暂时还没有完善")
        
    # Abaqus 接口相关
    def _find_abaqus_executable(self):
        """
        查找 Abaqus 可执行文件路径。
        优先顺序：
        1. 使用之前缓存路径（如果存在）
        2. 尝试系统 PATH 中的 'abaqus' 命令
        3. 尝试常见的 Windows 安装路径
        4. 如果都找不到，弹出对话框让用户手动选择
        """
        import os
        import platform
        
        # 如果之前已经找到并缓存了，检查是否是 Abaqus 6.14
        # 如果不是 6.14，清除缓存并重新查找（优先使用 6.14）
        if self.abaqus_executable and os.path.exists(self.abaqus_executable):
            # 检查文件名是否包含 614 或 6.14
            basename = os.path.basename(self.abaqus_executable).lower()
            if "614" in basename or "6.14" in basename:
                return self.abaqus_executable
            else:
                # 缓存的是其他版本，清除缓存，重新查找 6.14
                self.abaqus_executable = None
        
        # 1. 先尝试系统 PATH 中的 'abaqus' 命令
        try:
            result = subprocess.run(["abaqus", "information=version"], 
                                  capture_output=True, timeout=2)
            if result.returncode == 0 or result.returncode == 1:  # Abaqus 可能返回非0但命令存在
                self.abaqus_executable = "abaqus"
                return self.abaqus_executable
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # 2. 尝试常见的 Windows 安装路径（优先查找 Abaqus 6.14）
        if platform.system() == "Windows":
            # 优先查找 Abaqus 6.14 的路径
            abaqus_614_paths = [
                r"C:\SIMULIA\Commands\abq614.bat",
                r"C:\SIMULIA\Commands\abq6.14.bat",
                r"C:\SIMULIA\Abaqus\Commands\abq614.bat",
                r"C:\SIMULIA\Abaqus\Commands\abq6.14.bat",
            ]
            
            # 先检查 Abaqus 6.14 的特定路径
            for path in abaqus_614_paths:
                if os.path.exists(path):
                    self.abaqus_executable = path
                    return path
            
            # 也尝试查找 SIMULIA 目录下的所有 abq*.bat，优先选择包含 "614" 或 "6.14" 的
            simulia_bases = [
                r"C:\SIMULIA\Commands",
                r"C:\SIMULIA\Abaqus\Commands",
            ]
            
            # 先收集所有目录中的文件，优先选择 614
            all_bat_files_614 = []  # 包含 614 的文件
            all_bat_files_other = []  # 其他版本的文件
            
            for simulia_base in simulia_bases:
                if os.path.exists(simulia_base):
                    try:
                        for name in os.listdir(simulia_base):
                            if name.startswith("abq") and name.endswith(".bat"):
                                full_path = os.path.join(simulia_base, name)
                                if os.path.exists(full_path):
                                    basename = name.lower()
                                    if "614" in basename or "6.14" in basename:
                                        all_bat_files_614.append(full_path)
                                    else:
                                        all_bat_files_other.append(full_path)
                    except OSError:
                        pass
            
            # 优先返回包含 614 的文件
            if all_bat_files_614:
                # 如果有多个 614 版本，选择第一个
                self.abaqus_executable = all_bat_files_614[0]
                return all_bat_files_614[0]
            
            # 如果没找到 614，不自动选择其他版本，而是让用户手动选择
            # 这样可以确保用户使用的是 6.14 版本
        
        # 3. 如果都找不到，弹出对话框让用户手动选择
        from PyQt5.QtWidgets import QFileDialog
        reply = QMessageBox.question(
            self,
            "未找到 Abaqus 6.14",
            "无法自动找到 Abaqus 6.14 安装路径。\n"
            "是否手动选择 Abaqus 6.14 可执行文件？\n\n"
            "（通常位于 C:\\SIMULIA\\Commands\\ 目录下，文件名为 abq614.bat 或 abq6.14.bat）",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择 Abaqus 6.14 可执行文件",
                r"C:\SIMULIA\Commands",
                "Batch Files (*.bat);;Executable Files (*.exe);;All Files (*)"
            )
            if file_path and os.path.exists(file_path):
                self.abaqus_executable = file_path
                return file_path
        
        return None
    
    def launch_abaqus_cae(self):
        """
        基于文件的异步交互模式：
        
        第一步（启动）：
        - 用户点击按钮，选择 .inp 文件的保存路径（目录）
        - 程序记录路径，启动 Abaqus，按钮变为"等待导入"
        
        第二步（导入）：
        - 用户再次点击按钮（确认已完成建模）
        - 检查路径下是否存在 .inp 文件，如果存在则加载
        """
        from PyQt5.QtWidgets import QFileDialog
        import os
        
        # 如果处于"等待导入"状态，执行第二步：检查并导入
        if self.abaqus_waiting_for_import:
            self._import_abaqus_inp()
            return
        
        # 第一步：启动 Abaqus
        # 先查找 Abaqus 可执行文件
        abaqus_cmd = self._find_abaqus_executable()
        if not abaqus_cmd:
            QMessageBox.critical(
                self,
                "Abaqus Not Found",
                "无法找到 Abaqus 可执行文件。\n"
                "请确认已正确安装 Abaqus。"
            )
            return
        
        # 让用户选择 .inp 文件的保存路径（目录）
        inp_dir = QFileDialog.getExistingDirectory(
            self,
            "选择 INP 文件的保存路径（Abaqus 将在此目录下生成 .inp 文件）",
            ""
        )
        if not inp_dir:
            return
        
        # 记录路径
        self.abaqus_inp_path = inp_dir
        
        try:
            # 启动 Abaqus/CAE，并将工作目录设置为用户选择的文件夹
            if abaqus_cmd.endswith('.bat'):
                # Windows 上执行 .bat 文件，设置工作目录
                subprocess.Popen(
                    ["cmd", "/c", abaqus_cmd, "cae"],
                    cwd=inp_dir,
                    creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
                )
            else:
                # 直接命令（如 "abaqus"），设置工作目录
                subprocess.Popen([abaqus_cmd, "cae"], cwd=inp_dir)
            
            # 更新状态
            self.abaqus_waiting_for_import = True
            self.abaqus_action.setText("等待导入 INP...")
            
            self.message_area.appendPlainText(
                f"Abaqus/CAE 已启动（使用：{os.path.basename(abaqus_cmd)}）\n"
                f"工作目录：{inp_dir}\n"
                f"请在 Abaqus 中建模并导出 INP 文件到此目录，完成后点击 '等待导入 INP...' 按钮。\n"
            )
            self.statusBar.showMessage(f"Abaqus/CAE launched - 等待导入 INP 文件")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Abaqus Error",
                f"启动 Abaqus/CAE 失败：{e}\n\n"
                f"尝试使用的命令：{abaqus_cmd}"
            )
    
    def _import_abaqus_inp(self):
        """
        第二步：检查并导入 INP 文件
        """
        import os
        
        if not self.abaqus_inp_path:
            QMessageBox.warning(
                self,
                "错误",
                "未找到保存路径，请重新启动 Abaqus 建模流程。"
            )
            return
        
        # 检查目录下是否存在 .inp 文件
        inp_files = []
        try:
            for name in os.listdir(self.abaqus_inp_path):
                if name.lower().endswith(".inp"):
                    full = os.path.join(self.abaqus_inp_path, name)
                    if os.path.exists(full):
                        inp_files.append(full)
        except OSError as e:
            QMessageBox.critical(
                self,
                "错误",
                f"无法访问目录：{self.abaqus_inp_path}\n错误：{e}"
            )
            return
        
        if not inp_files:
            QMessageBox.warning(
                self,
                "未找到 INP 文件",
                f"在目录中未找到 .inp 文件：\n{self.abaqus_inp_path}\n\n"
                "请确认已在 Abaqus 中导出 INP 文件到此目录。"
            )
            return
        
        # 如果只有一个文件，直接加载
        # 如果有多个文件，选择最新的（按修改时间）
        if len(inp_files) == 1:
            inp_file = inp_files[0]
        else:
            # 多个文件，选择最新的
            inp_files_with_mtime = []
            for f in inp_files:
                try:
                    mtime = os.path.getmtime(f)
                    inp_files_with_mtime.append((mtime, f))
                except OSError:
                    continue
            
            if not inp_files_with_mtime:
                QMessageBox.warning(
                    self,
                    "错误",
                    "无法获取文件信息。"
                )
                return
            
            inp_files_with_mtime.sort(reverse=True)
            inp_file = inp_files_with_mtime[0][1]
            
            # 如果多个文件，询问用户是否加载最新的
            if len(inp_files) > 1:
                file_list = "\n".join([os.path.basename(f) for f in inp_files])
                reply = QMessageBox.question(
                    self,
                    "多个 INP 文件",
                    f"找到 {len(inp_files)} 个 INP 文件：\n\n{file_list}\n\n"
                    f"是否加载最新的文件：{os.path.basename(inp_file)}？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.No:
                    return
        
        # 加载 INP 文件
        self.message_area.appendPlainText(
            f"正在加载 INP 文件：{os.path.basename(inp_file)}\n"
        )
        self.statusBar.showMessage(f"正在加载 INP: {os.path.basename(inp_file)}")
        
        # 调用解析函数（占位）
        self.parse_inp(inp_file)
        
        # 重置状态
        self.abaqus_waiting_for_import = False
        self.abaqus_action.setText("Abaqus Modeling...")
        self.abaqus_inp_path = None
    
    def parse_inp(self, path):
        """
        解析 INP 文件的占位函数。
        
        Args:
            path: INP 文件路径
        """
        # 这里调用现有的 load_inp_file 函数
        self.load_inp_file(path)

    # 插件和帮助方法
    def plugin_manager(self):
        QMessageBox.information(self, "Plugin Manager", "插件管理器暂时还没有完善")
        
    def help_context(self):
        QMessageBox.information(self, "Help", "上下文帮助暂时还没有完善")
        
    def about(self):
        """关于对话框"""
        QMessageBox.about(self, "About PyAbaqus/CAE", 
                         "PyAbaqus/CAE - A Finite Element Analysis Tool\n"
                         "Version 1.0\n"
                         "Built with Python, PyQt5, and PyVista")
    
    def _set_message_area_height(self, dock_widget):
        """设置 Message Area 的初始高度"""
        if dock_widget.isVisible():
            # 获取当前 DockWidget 的大小
            current_size = dock_widget.size()
            # 设置高度为 80px（更矮的初始高度）
            dock_widget.resize(current_size.width(), 80)
    
    def _set_toolbox_height(self, dock_widget):
        """设置 Toolbox 的初始高度"""
        if dock_widget.isVisible():
            # 获取当前 DockWidget 的大小
            current_size = dock_widget.size()
            # 设置高度为 150px（更矮的初始高度）
            dock_widget.resize(current_size.width(), 150)
    
    def closeEvent(self, event):
        """窗口关闭事件 - 确保线程正确清理"""
        # 关闭监控对话框
        if self.monitor_dialog is not None:
            self.monitor_dialog.close()
            self.monitor_dialog = None
        
        if self.worker is not None and self.worker.isRunning():
            # 请求线程停止
            self.worker.requestInterruption()
            # 等待线程完成（最多等待3秒）
            if not self.worker.wait(3000):
                # 如果3秒内未完成，强制终止
                self.worker.terminate()
                self.worker.wait()
            self.worker = None
        # 接受关闭事件
        event.accept()