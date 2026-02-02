# 文件: PyMFEA/main.py
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from gui.app import MainWindow

def main():
    # 1. [关键] 开启高DPI缩放，解决 2K/4K 屏字体极小的问题
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)

    # 2. [关键] 设置工业软件标准字体 (Segoe UI 或 Tahoma, 10pt-12pt)
    # Abaqus 风格通常使用无衬线字体，字号不能太小
    font = QFont("Segoe UI", 10) 
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    # 3. 应用样式表 (见下文)
    app.setStyleSheet(get_abaqus_style())

    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

def get_abaqus_style():
    """
    定义 Abaqus 风格的 QSS 样式表
    解决了: 字太小、控件太挤、表头不明显的问题
    使用工业灰 (#F0F0F0) 作为基调，增加控件间距
    """
    return """
    /* 全局设定 - 工业灰基调 */
    QWidget {
        color: #000000;
        background-color: #F0F0F0; /* 经典工业灰 */
        font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
        font-size: 10pt; /* 使用 pt 单位，配合 HighDPI 自动缩放 */
    }
    
    /* 主窗口背景 */
    QMainWindow {
        background-color: #F0F0F0;
    }
    
    /* DockWidget 优化 */
    QDockWidget {
        background-color: #F0F0F0;
        border: 1px solid #A0A0A0;
    }
    QDockWidget::title {
        background: qlineargradient(
            x1:0, y1:0, x2:0, y2:1,
            stop:0 #E0E0E0, stop:1 #D0D0D0
        );
        padding: 6px 8px;
        border-bottom: 1px solid #A0A0A0;
        font-weight: bold;
        font-size: 10pt;
    }
    
    /* ScrollArea 优化 */
    QScrollArea {
        background-color: #F0F0F0;
        border: none;
    }
    QScrollBar:vertical {
        background-color: #E0E0E0;
        width: 12px;
        border: none;
    }
    QScrollBar::handle:vertical {
        background-color: #B0B0B0;
        min-height: 20px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #909090;
    }
    
    /* Model Tree (QTreeWidget) 优化 */
    QTreeWidget {
        border: 1px solid #A0A0A0;
        background-color: #FFFFFF;
        alternate-background-color: #F8F8F8;
    }
    QTreeWidget::item {
        height: 32px; /* 增加行高，提升可读性 */
        padding: 6px 8px; /* 增加内边距 */
        border-bottom: 1px solid #F0F0F0;
    }
    QTreeWidget::item:hover {
        background-color: #E8F4FD;
    }
    QTreeWidget::item:selected {
        background-color: #A0C4E8;
        color: #000000;
    }
    QHeaderView::section {
        background-color: #DDDDDD; /* Abaqus 风格表头背景 */
        padding: 6px 8px; /* 增加表头内边距 */
        border: 1px solid #A0A0A0;
        border-bottom: 2px solid #808080;
        font-weight: bold;
        font-size: 10pt;
        height: 32px; /* 增加表头高度 */
    }

    /* Toolbox / GroupBox 优化 - 紧凑化 */
    QGroupBox {
        border: 1px solid #A0A0A0;
        margin-top: 16px; /* 减小顶部间距 */
        margin-bottom: 6px; /* 减小底部间距 */
        padding-top: 8px; /* 减小顶部内边距 */
        font-weight: bold;
        font-size: 10pt;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 6px; /* 减小标题左右内边距 */
        color: #333333;
    }
    
    /* 按钮样式 - 默认 */
    QPushButton {
        background-color: #E1E1E1;
        border: 1px solid #ADADAD;
        padding: 8px 16px; /* 增加按钮内边距 */
        border-radius: 2px;
        min-height: 28px; /* 增加最小高度 */
        font-size: 10pt;
        margin: 2px; /* 增加按钮间距 */
    }
    
    /* Toolbox 内的按钮样式 - 紧凑化（通过更具体的选择器） */
    QScrollArea QPushButton {
        background-color: #E1E1E1;
        border: 1px solid #ADADAD;
        padding: 4px 12px; /* 减小按钮内边距 */
        border-radius: 2px;
        min-height: 24px; /* 减小最小高度 */
        font-size: 10pt;
        margin: 1px; /* 减小按钮间距 */
    }
    QPushButton:hover {
        background-color: #E5F1FB;
        border: 1px solid #0078D7;
    }
    QPushButton:pressed {
        background-color: #CCE4F7;
        border: 1px inset #0078D7;
    }
    
    /* 输入框优化 - 增加间距 */
    QLineEdit, QComboBox {
        border: 1px solid #A0A0A0;
        padding: 6px 8px; /* 增加内边距 */
        background-color: white;
        min-height: 28px; /* 保证输入框高度 */
        font-size: 10pt;
        margin: 2px; /* 增加控件间距 */
    }
    QComboBox::drop-down {
        border: none;
        width: 20px;
    }
    QComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 6px solid #333333;
        margin-right: 4px;
    }
    
    /* CheckBox 优化 */
    QCheckBox {
        spacing: 8px; /* 增加文字与复选框间距 */
        font-size: 10pt;
        padding: 4px;
    }
    QCheckBox::indicator {
        width: 18px;
        height: 18px;
        border: 1px solid #A0A0A0;
        background-color: white;
    }
    QCheckBox::indicator:checked {
        background-color: #0078D7;
        border-color: #0078D7;
    }
    
    /* SpinBox 优化 */
    QDoubleSpinBox, QSpinBox {
        border: 1px solid #A0A0A0;
        padding: 6px 8px;
        background-color: white;
        min-height: 28px;
        font-size: 10pt;
        margin: 2px;
    }
    
    /* Label 优化 */
    QLabel {
        font-size: 10pt;
        padding: 4px;
        color: #000000;
    }
    
    /* 工具栏优化 */
    QToolBar {
        background-color: #E6F3FF;
        border: 1px inset #808080;
        spacing: 4px; /* 增加工具栏控件间距 */
    }
    QToolButton {
        padding: 4px;
        margin: 2px;
    }
    
    /* 菜单栏优化 */
    QMenuBar {
        background-color: #E6F3FF;
        color: #000000;
        border-bottom: 1px inset #808080;
        padding: 2px;
    }
    QMenuBar::item {
        padding: 4px 12px; /* 增加菜单项内边距 */
        background-color: transparent;
    }
    QMenuBar::item:selected {
        background-color: #0066CC;
        color: white;
    }
    QMenu {
        background-color: #E6F3FF;
        border: 1px outset #808080;
        padding: 4px;
    }
    QMenu::item {
        padding: 6px 24px; /* 增加菜单项内边距 */
    }
    QMenu::item:selected {
        background-color: #0066CC;
        color: white;
    }
    
    /* 状态栏优化 */
    QStatusBar {
        background-color: #E6F3FF;
        border-top: 1px inset #808080;
        padding: 4px;
    }
    
    /* 文本编辑区优化 */
    QTextEdit, QPlainTextEdit {
        background-color: white;
        border: 1px inset #808080;
        font-family: 'Courier New', monospace;
        font-size: 10pt;
        padding: 4px;
    }
    """

if __name__ == "__main__":
    main()