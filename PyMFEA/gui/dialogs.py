import numpy as np
import csv
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QFileDialog,
                             QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox, 
                             QGroupBox, QDialogButtonBox, QLabel, QCheckBox)
from PyQt5.QtCore import Qt

class DataViewerDialog(QDialog):
    """
    通用数据查看器窗口
    用于显示 Node 和 Element 的详细数据表格
    """
    def __init__(self, title, headers, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 500) # 默认窗口大小
        
        # 保存数据用于导出
        self.headers = headers
        self.data = data
        self.title = title
        
        # 设置窗口非模态（允许同时操作主界面）
        self.setModal(False)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建顶部工具栏（包含导出按钮）
        toolbar_layout = QHBoxLayout()
        toolbar_layout.addStretch()  # 左侧弹性空间，将按钮推到右侧
        
        # 导出CSV按钮
        self.btn_export_csv = QPushButton("导出 CSV")
        self.btn_export_csv.setMinimumSize(100, 32)  # 增加宽度，确保文字完整显示
        self.btn_export_csv.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 10pt;
            }
        """)
        self.btn_export_csv.clicked.connect(self.export_to_csv)
        toolbar_layout.addWidget(self.btn_export_csv)
        
        # 导出TXT按钮
        self.btn_export_txt = QPushButton("导出 TXT")
        self.btn_export_txt.setMinimumSize(100, 32)  # 增加宽度，确保文字完整显示
        self.btn_export_txt.setStyleSheet("""
            QPushButton {
                padding: 4px 8px;
                font-size: 10pt;
            }
        """)
        self.btn_export_txt.clicked.connect(self.export_to_txt)
        toolbar_layout.addWidget(self.btn_export_txt)
        
        layout.addLayout(toolbar_layout)
        
        # 表格控件
        self.table = QTableWidget()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # 隐藏垂直表头（默认的行号），我们通常把ID放在第一列
        self.table.verticalHeader().setVisible(False)
        
        # 设置样式
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #d0d0d0;
                font-family: "Segoe UI", "Arial";
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 4px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
            }
        """)
        
        # 优化列宽显示
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.table)
        
        # 填充数据
        self.populate_data(data)
        
    def populate_data(self, data):
        """
        填充数据到表格
        data: list of lists (rows)
        """
        if not data:
            return

        rows = len(data)
        cols = len(data[0]) if rows > 0 else 0
        
        self.table.setRowCount(rows)
        
        # 禁用更新以提高大量数据时的填充速度
        self.table.setUpdatesEnabled(False)
        
        for i in range(rows):
            for j in range(cols):
                val = data[i][j]
                
                # 格式化文本
                if isinstance(val, float):
                    text = f"{val:.4f}" # 浮点数保留4位
                else:
                    text = str(val)
                
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter) # 居中对齐
                item.setFlags(item.flags() ^ Qt.ItemIsEditable) # 设置为只读
                
                self.table.setItem(i, j, item)
                
        self.table.setUpdatesEnabled(True)
    
    def export_to_csv(self):
        """导出数据为CSV格式"""
        if not self.data:
            return
        
        # 获取保存路径
        default_filename = f"{self.title.replace(' ', '_')}.csv"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "导出为CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(self.headers)
                # 写入数据
                writer.writerows(self.data)
            
            # 显示成功消息
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "导出成功", f"数据已成功导出到：\n{filepath}")
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "导出失败", f"导出CSV文件时出错：\n{str(e)}")
    
    def export_to_txt(self):
        """导出数据为TXT格式（制表符分隔）"""
        if not self.data:
            return
        
        # 获取保存路径
        default_filename = f"{self.title.replace(' ', '_')}.txt"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "导出为TXT",
            default_filename,
            "Text Files (*.txt);;All Files (*)"
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入表头（制表符分隔）
                f.write('\t'.join(self.headers) + '\n')
                # 写入数据
                for row in self.data:
                    # 将每行数据转换为字符串，用制表符分隔
                    row_str = '\t'.join(str(val) for val in row)
                    f.write(row_str + '\n')
            
            # 显示成功消息
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "导出成功", f"数据已成功导出到：\n{filepath}")
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "导出失败", f"导出TXT文件时出错：\n{str(e)}")

class SolverSettingsDialog(QDialog):
    """
    求解器参数配置对话框
    允许用户选择分析类型 (Linear/TL/UL) 并配置时间步和收敛参数
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Job - Solver Settings")
        self.resize(450, 400)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 1. 分析类型选择 ===
        grp_type = QGroupBox("Analysis Type")
        form_type = QFormLayout()
        form_type.setSpacing(10)
        
        self.combo_analysis = QComboBox()
        self.combo_analysis.addItems([
            "Linear Elastic (Small Deformation)", 
            "Nonlinear TL (Total Lagrangian - Metal)", 
            "Nonlinear UL (Updated Lagrangian - Rubber)"
        ])
        # 添加工具提示解释区别
        self.combo_analysis.setItemData(0, "标准线性有限元 (F=KU)", Qt.ToolTipRole)
        self.combo_analysis.setItemData(1, "基于初始构型计算，适用于金属弹塑性等中等大变形", Qt.ToolTipRole)
        self.combo_analysis.setItemData(2, "基于当前构型计算，适用于橡胶等超大变形", Qt.ToolTipRole)
        
        form_type.addRow("Formulation:", self.combo_analysis)
        grp_type.setLayout(form_type)
        layout.addWidget(grp_type)

        # === 2. 时间步控制 (仅非线性) ===
        self.grp_time = QGroupBox("Time Stepping (Nonlinear Only)")
        form_time = QFormLayout()
        
        self.spin_time_total = QDoubleSpinBox()
        self.spin_time_total.setValue(1.0)
        self.spin_time_total.setRange(0.001, 10000.0)
        self.spin_time_total.setSuffix(" s")
        self.spin_time_total.setToolTip("总分析时间 (Total Time Period)")
        
        self.spin_dt_initial = QDoubleSpinBox()
        self.spin_dt_initial.setValue(0.05)
        self.spin_dt_initial.setRange(1e-6, 1.0)
        self.spin_dt_initial.setDecimals(4)
        self.spin_dt_initial.setSingleStep(0.1)  # 每次点击变化 0.001
        self.spin_dt_initial.setSuffix(" s")
        self.spin_dt_initial.setToolTip("初始增量步长 (Initial Time Increment)")

        form_time.addRow("Total Time:", self.spin_time_total)
        form_time.addRow("Initial Step:", self.spin_dt_initial)
        self.grp_time.setLayout(form_time)
        layout.addWidget(self.grp_time)

        # === 3. 收敛控制 (仅非线性) ===
        self.grp_conv = QGroupBox("Convergence (Nonlinear Only)")
        form_conv = QFormLayout()
        
        self.spin_max_iter = QSpinBox()
        self.spin_max_iter.setValue(15)
        self.spin_max_iter.setRange(5, 500)
        self.spin_max_iter.setToolTip("每个增量步的最大迭代次数")
        
        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setValue(1e-3)
        self.spin_tol.setRange(1e-9, 0.1)
        self.spin_tol.setDecimals(6)
        self.spin_tol.setSingleStep(0.0001)  # 每次点击变化 0.0001
        self.spin_tol.setToolTip("残差力收敛容差 (Force Residual Tolerance)")
        
        form_conv.addRow("Max Iterations:", self.spin_max_iter)
        form_conv.addRow("Tolerance:", self.spin_tol)
        self.grp_conv.setLayout(form_conv)
        layout.addWidget(self.grp_conv)

        # === 4. 底部按钮 ===
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 信号连接：根据选择禁用/启用非线性选项
        self.combo_analysis.currentIndexChanged.connect(self.on_type_changed)
        
        # 初始化状态
        self.on_type_changed(0)

    def on_type_changed(self, index):
        """
        线性模式(index=0)下，禁用时间步和收敛设置
        """
        is_nonlinear = (index > 0)
        self.grp_time.setEnabled(is_nonlinear)
        self.grp_conv.setEnabled(is_nonlinear)

    def get_settings(self):
        """
        返回配置字典，供 Worker 和 Solver 使用
        """
        idx = self.combo_analysis.currentIndex()
        if idx == 0: 
            type_str = "Linear"
        elif idx == 1: 
            type_str = "TL"
        else: 
            type_str = "UL"
        
        return {
            "type": type_str,
            "total_time": self.spin_time_total.value(),
            "initial_dt": self.spin_dt_initial.value(),
            "max_iter": self.spin_max_iter.value(),
            "tolerance": self.spin_tol.value()
        }


class MaterialPropertiesDialog(QDialog):
    """
    材料属性对话框 - 支持弹性和塑性参数
    
    用于在 GUI 中编辑材料属性，包括：
    - 弹性参数 (E, nu)
    - 塑性参数 (yield_stress)
    """
    def __init__(self, current_props=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Material Properties")
        self.resize(400, 300)
        
        # 当前属性 (用于初始化控件)
        self.current_props = current_props or {"E": 70000.0, "nu": 0.3}
        
        self.setup_ui()
        self.load_current_values()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # === 1. 弹性属性组 ===
        grp_elastic = QGroupBox("Elastic Properties")
        form_elastic = QFormLayout()
        form_elastic.setSpacing(10)
        
        self.spin_E = QDoubleSpinBox()
        self.spin_E.setRange(1.0, 1e12)
        self.spin_E.setDecimals(1)
        self.spin_E.setValue(70000.0)
        self.spin_E.setSuffix(" MPa")
        self.spin_E.setToolTip("Young's Modulus (弹性模量)")
        
        self.spin_nu = QDoubleSpinBox()
        self.spin_nu.setRange(0.0, 0.499)
        self.spin_nu.setDecimals(3)
        self.spin_nu.setSingleStep(0.01)
        self.spin_nu.setValue(0.3)
        self.spin_nu.setToolTip("Poisson's Ratio (泊松比), 范围 [0, 0.5)")
        
        form_elastic.addRow("Young's Modulus (E):", self.spin_E)
        form_elastic.addRow("Poisson's Ratio (ν):", self.spin_nu)
        grp_elastic.setLayout(form_elastic)
        layout.addWidget(grp_elastic)
        
        # === 2. 塑性属性组 ===
        grp_plastic = QGroupBox("Plastic Properties")
        form_plastic = QFormLayout()
        form_plastic.setSpacing(10)
        
        self.chk_plastic = QCheckBox("Enable Plasticity (启用塑性)")
        self.chk_plastic.setToolTip("勾选后启用 J2 理想塑性模型")
        self.chk_plastic.stateChanged.connect(self.on_plastic_toggled)
        form_plastic.addRow(self.chk_plastic)
        
        self.spin_yield = QDoubleSpinBox()
        self.spin_yield.setRange(1.0, 1e9)
        self.spin_yield.setDecimals(1)
        self.spin_yield.setValue(200.0)
        self.spin_yield.setSuffix(" MPa")
        self.spin_yield.setToolTip("Yield Stress (屈服应力)")
        self.spin_yield.setEnabled(False)  # 默认禁用
        
        form_plastic.addRow("Yield Stress (σy):", self.spin_yield)
        grp_plastic.setLayout(form_plastic)
        layout.addWidget(grp_plastic)
        
        # === 3. 底部按钮 ===
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def on_plastic_toggled(self, state):
        """塑性复选框状态改变时，启用/禁用屈服应力输入"""
        self.spin_yield.setEnabled(state == Qt.Checked)
    
    def load_current_values(self):
        """从当前属性加载值到控件"""
        if self.current_props:
            self.spin_E.setValue(self.current_props.get("E", 70000.0))
            self.spin_nu.setValue(self.current_props.get("nu", 0.3))
            
            # 检查是否有塑性参数
            plastic = self.current_props.get("plastic")
            if plastic:
                self.chk_plastic.setChecked(True)
                self.spin_yield.setValue(plastic.get("yield_stress", 200.0))
    
    def get_properties(self):
        """
        获取用户输入的材料属性
        
        Returns:
            dict: 材料属性字典，与 worker.py 的 material_props 格式一致
        """
        props = {
            "E": self.spin_E.value(),
            "nu": self.spin_nu.value()
        }
        
        if self.chk_plastic.isChecked():
            props["plastic"] = {
                "yield_stress": self.spin_yield.value(),
                "hardening": 0.0  # 理想塑性
            }
        
        return props