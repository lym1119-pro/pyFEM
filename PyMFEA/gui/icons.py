"""
图标管理模块 - 提供统一的图标接口
使用 PyQt5 标准图标和自定义绘制图标
"""
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPolygon
from PyQt5.QtWidgets import QStyle
from PyQt5.QtCore import Qt, QSize, QPoint


class IconManager:
    """图标管理器 - 单例模式"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._style = None
        self._init_icons()
    
    def set_style(self, style):
        """设置样式对象（用于获取标准图标）"""
        self._style = style
    
    def _init_icons(self):
        """初始化所有图标"""
        self.icons = {}
        
    def _get_standard_icon(self, standard_pixmap):
        """获取标准图标"""
        if self._style:
            return self._style.standardIcon(standard_pixmap)
        return QIcon()
    
    def _create_icon(self, draw_func, size=16, color=None):
        """创建自定义绘制图标"""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if color is None:
            color = QColor(70, 70, 70)  # 默认深灰色
        
        draw_func(painter, size, color)
        painter.end()
        return QIcon(pixmap)
    
    # ========== 文件操作图标 ==========
    def new_file(self):
        """新建文件"""
        return self._get_standard_icon(QStyle.SP_FileIcon)
    
    def open_file(self):
        """打开文件"""
        return self._get_standard_icon(QStyle.SP_DirOpenIcon)
    
    def save_file(self):
        """保存文件"""
        return self._get_standard_icon(QStyle.SP_DriveFDIcon)
    
    def import_file(self):
        """导入文件"""
        def draw(painter, size, color):
            pen = QPen(color, 2)
            painter.setPen(pen)
            # 绘制向下箭头
            arrow_size = size * 0.4
            center_x, center_y = size / 2, size / 2
            painter.drawLine(int(center_x), int(center_y - arrow_size/2), int(center_x), int(center_y + arrow_size/2))
            painter.drawLine(int(center_x - arrow_size/3), int(center_y), int(center_x), int(center_y - arrow_size/2))
            painter.drawLine(int(center_x + arrow_size/3), int(center_y), int(center_x), int(center_y - arrow_size/2))
        return self._create_icon(draw, color=QColor(0, 120, 215))
    
    def export_file(self):
        """导出文件"""
        def draw(painter, size, color):
            pen = QPen(color, 2)
            painter.setPen(pen)
            # 绘制向上箭头
            arrow_size = size * 0.4
            center_x, center_y = size / 2, size / 2
            painter.drawLine(int(center_x), int(center_y - arrow_size/2), int(center_x), int(center_y + arrow_size/2))
            painter.drawLine(int(center_x - arrow_size/3), int(center_y), int(center_x), int(center_y + arrow_size/2))
            painter.drawLine(int(center_x + arrow_size/3), int(center_y), int(center_x), int(center_y + arrow_size/2))
        return self._create_icon(draw, color=QColor(0, 120, 215))
    
    # ========== 视图操作图标 ==========
    def view_front(self):
        """前视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            # 绘制立方体前视图（正方形）
            painter.drawRect(int(margin), int(margin), int(size - 2*margin), int(size - 2*margin))
        return self._create_icon(draw)
    
    def view_back(self):
        """后视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            # 绘制立方体后视图（带虚线表示背面）
            painter.drawRect(int(margin), int(margin), int(size - 2*margin), int(size - 2*margin))
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(int(margin + 2), int(margin + 2), int(size - 2*margin - 4), int(size - 2*margin - 4))
        return self._create_icon(draw)
    
    def view_left(self):
        """左视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            # 绘制立方体左视图（矩形）
            w = (size - 2*margin) * 0.6
            h = size - 2*margin
            painter.drawRect(int(margin), int(margin), int(w), int(h))
        return self._create_icon(draw)
    
    def view_right(self):
        """右视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            # 绘制立方体右视图（矩形）
            w = (size - 2*margin) * 0.6
            h = size - 2*margin
            painter.drawRect(int(size - margin - w), int(margin), int(w), int(h))
        return self._create_icon(draw)
    
    def view_top(self):
        """顶视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            # 绘制立方体顶视图（矩形）
            w = size - 2*margin
            h = (size - 2*margin) * 0.6
            painter.drawRect(int(margin), int(margin), int(w), int(h))
        return self._create_icon(draw)
    
    def view_bottom(self):
        """底视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            # 绘制立方体底视图（矩形）
            w = size - 2*margin
            h = (size - 2*margin) * 0.6
            painter.drawRect(int(margin), int(size - margin - h), int(w), int(h))
        return self._create_icon(draw)
    
    def view_iso(self):
        """等轴视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            # 绘制等轴立方体
            points = [
                QPoint(int(margin), int(size - margin)),  # 左下
                QPoint(int(size - margin), int(size - margin)),  # 右下
                QPoint(int(size - margin * 1.5), int(margin)),  # 右上
                QPoint(int(margin * 0.5), int(margin)),  # 左上
            ]
            # 前面
            painter.drawPolygon(QPolygon(points))
            # 顶面
            top_points = [
                QPoint(int(margin * 0.5), int(margin)),
                QPoint(int(size - margin * 1.5), int(margin)),
                QPoint(int(size - margin), int(size - margin)),
                QPoint(int(margin), int(size - margin)),
            ]
            painter.drawPolygon(QPolygon(top_points))
        return self._create_icon(draw)
    
    def reset_view(self):
        """重置视图"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            # 绘制重置图标（圆形箭头）
            center_x, center_y = size / 2, size / 2
            radius = size * 0.3
            painter.drawArc(int(center_x - radius), int(center_y - radius), 
                          int(radius * 2), int(radius * 2), 45 * 16, 270 * 16)
            # 箭头
            arrow_size = size * 0.15
            painter.drawLine(int(center_x + radius * 0.7), int(center_y - radius * 0.7),
                           int(center_x + radius * 0.7 + arrow_size), int(center_y - radius * 0.7 - arrow_size))
            painter.drawLine(int(center_x + radius * 0.7), int(center_y - radius * 0.7),
                           int(center_x + radius * 0.7 + arrow_size), int(center_y - radius * 0.7 + arrow_size))
        return self._create_icon(draw)
    
    # ========== 模型操作图标 ==========
    def create_part(self):
        """创建零件"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            painter.setBrush(QBrush(color.lighter(150)))
            margin = size * 0.2
            # 绘制立方体
            points = [
                QPoint(int(margin), int(size - margin)),
                QPoint(int(size - margin), int(size - margin)),
                QPoint(int(size - margin * 1.3), int(margin)),
                QPoint(int(margin * 0.3), int(margin)),
            ]
            painter.drawPolygon(QPolygon(points))
        return self._create_icon(draw, color=QColor(0, 150, 0))
    
    def create_material(self):
        """创建材料"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            painter.setBrush(QBrush(color.lighter(150)))
            center_x, center_y = size / 2, size / 2
            radius = size * 0.35
            painter.drawEllipse(int(center_x - radius), int(center_y - radius),
                              int(radius * 2), int(radius * 2))
        return self._create_icon(draw, color=QColor(200, 0, 0))
    
    def mesh(self):
        """网格"""
        def draw(painter, size, color):
            pen = QPen(color, 1)
            painter.setPen(pen)
            margin = size * 0.2
            step = (size - 2*margin) / 4
            # 绘制网格线
            for i in range(5):
                y = margin + i * step
                painter.drawLine(int(margin), int(y), int(size - margin), int(y))
            for i in range(5):
                x = margin + i * step
                painter.drawLine(int(x), int(margin), int(x), int(size - margin))
        return self._create_icon(draw, color=QColor(0, 150, 150))
    
    def run_solver(self):
        """运行求解器"""
        def draw(painter, size, color):
            pen = QPen(color, 2)
            painter.setPen(pen)
            # 绘制播放按钮（三角形）
            margin = size * 0.25
            points = [
                QPoint(int(margin), int(margin)),
                QPoint(int(size - margin), int(size / 2)),
                QPoint(int(margin), int(size - margin)),
            ]
            painter.setBrush(QBrush(color))
            painter.drawPolygon(QPolygon(points))
        return self._create_icon(draw, color=QColor(0, 150, 0))
    
    def stop_solver(self):
        """停止求解器"""
        def draw(painter, size, color):
            pen = QPen(color, 2)
            painter.setPen(pen)
            painter.setBrush(QBrush(color))
            margin = size * 0.3
            painter.drawRect(int(margin), int(margin), int(size - 2*margin), int(size - 2*margin))
        return self._create_icon(draw, color=QColor(200, 0, 0))

    # ========== 其他建模相关图标（占位） ==========
    def create_section(self):
        """创建截面：深灰工字型/矩形"""
        def draw(painter, size, color):
            c = QColor(80, 80, 80)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(c))
            margin = size * 0.15
            # 顶/底翼缘 + 腹板
            painter.drawRect(int(margin), int(margin), int(size - 2 * margin), int(size * 0.2))
            painter.drawRect(int(size * 0.4), int(size * 0.2), int(size * 0.2), int(size * 0.6))
            painter.drawRect(int(margin), int(size * 0.8), int(size - 2 * margin), int(size * 0.2))
        return self._create_icon(draw, color=QColor(80, 80, 80))

    def create_step(self):
        """创建分析步：棕色时间轴/箭头"""
        def draw(painter, size, color):
            c = QColor(139, 69, 19)
            pen = QPen(c, 1.5)
            painter.setPen(pen)
            margin = size * 0.2
            mid_y = size / 2
            # 时间轴
            painter.drawLine(int(margin), int(mid_y), int(size - margin), int(mid_y))
            # 箭头
            painter.drawLine(int(size - margin), int(mid_y),
                             int(size - margin * 1.6), int(mid_y - margin * 0.8))
            painter.drawLine(int(size - margin), int(mid_y),
                             int(size - margin * 1.6), int(mid_y + margin * 0.8))
        return self._create_icon(draw, color=QColor(139, 69, 19))

    def create_interaction(self):
        """创建相互作用：蓝色接触链条/连接"""
        def draw(painter, size, color):
            c = QColor(0, 0, 180)
            pen = QPen(c, 1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            r = size * 0.18
            # 两个圆环 + 连线
            painter.drawEllipse(int(size * 0.2), int(size * 0.3), int(r * 2), int(r * 2))
            painter.drawEllipse(int(size * 0.6), int(size * 0.3), int(r * 2), int(r * 2))
            painter.drawLine(int(size * 0.2 + r * 2), int(size * 0.4),
                             int(size * 0.6), int(size * 0.4))
        return self._create_icon(draw, color=QColor(0, 0, 180))

    def create_load(self):
        """创建载荷：亮黄向下粗箭头"""
        def draw(painter, size, color):
            c = QColor(255, 200, 0)
            pen = QPen(c.darker(150), 2)
            painter.setPen(pen)
            painter.setBrush(QBrush(c))
            center_x = size / 2
            painter.drawLine(int(center_x), int(size * 0.15), int(center_x), int(size * 0.65))
            points = [
                QPoint(int(center_x - size * 0.2), int(size * 0.45)),
                QPoint(int(center_x), int(size * 0.85)),
                QPoint(int(center_x + size * 0.2), int(size * 0.45)),
            ]
            painter.drawPolygon(QPolygon(points))
        return self._create_icon(draw, color=QColor(255, 200, 0))

    def create_bc(self):
        """创建边界条件：橙色三角支座"""
        def draw(painter, size, color):
            c = QColor(255, 140, 0)
            painter.setPen(QPen(c.darker(150), 1))
            painter.setBrush(QBrush(c))
            base_y = size * 0.75
            tri = QPolygon([
                QPoint(int(size * 0.2), int(base_y)),
                QPoint(int(size * 0.8), int(base_y)),
                QPoint(int(size * 0.5), int(size * 0.25)),
            ])
            painter.drawPolygon(tri)
            painter.setPen(QPen(QColor(60, 60, 60), 1))
            painter.drawLine(int(size * 0.15), int(size * 0.85),
                             int(size * 0.85), int(size * 0.85))
        return self._create_icon(draw, color=QColor(255, 140, 0))

    def create_job(self):
        """创建作业：深绿计算机/运行符号"""
        def draw(painter, size, color):
            c = QColor(0, 100, 0)
            painter.setPen(QPen(c, 1.5))
            painter.setBrush(QBrush(c.lighter(160)))
            # 显示器
            margin = size * 0.15
            painter.drawRect(int(margin), int(margin),
                             int(size - 2 * margin), int(size * 0.5))
            # 底座
            painter.drawRect(int(size * 0.4), int(size * 0.65),
                             int(size * 0.2), int(size * 0.15))
            # 运行三角
            tri = QPolygon([
                QPoint(int(size * 0.45), int(size * 0.22)),
                QPoint(int(size * 0.7), int(size * 0.35)),
                QPoint(int(size * 0.45), int(size * 0.48)),
            ])
            painter.setBrush(QBrush(c))
            painter.drawPolygon(tri)
        return self._create_icon(draw, color=QColor(0, 100, 0))
    
    # ========== 工具图标 ==========
    def query(self):
        """查询工具"""
        def draw(painter, size, color):
            pen = QPen(color, 2)
            painter.setPen(pen)
            # 绘制问号
            center_x, center_y = size / 2, size / 2
            radius = size * 0.25
            painter.drawArc(int(center_x - radius), int(center_y - radius * 0.5),
                          int(radius * 2), int(radius * 2), 0, 180 * 16)
            painter.drawLine(int(center_x), int(center_y + radius * 0.5),
                           int(center_x), int(size - size * 0.2))
            painter.drawPoint(int(center_x), int(size - size * 0.15))
        return self._create_icon(draw)
    
    def measure(self):
        """测量工具"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            # 绘制尺子
            margin = size * 0.2
            painter.drawLine(int(margin), int(size / 2), int(size - margin), int(size / 2))
            # 刻度
            for i in range(5):
                x = margin + i * (size - 2*margin) / 4
                painter.drawLine(int(x), int(size / 2 - size * 0.1),
                                int(x), int(size / 2 + size * 0.1))
        return self._create_icon(draw)
    
    # ========== 其他图标 ==========
    def zoom_fit(self):
        """适应窗口"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            margin = size * 0.25
            # 绘制四个角
            corner_size = size * 0.15
            corners = [
                (margin, margin),  # 左上
                (size - margin, margin),  # 右上
                (size - margin, size - margin),  # 右下
                (margin, size - margin),  # 左下
            ]
            for x, y in corners:
                painter.drawLine(int(x), int(y), int(x + corner_size), int(y))
                painter.drawLine(int(x), int(y), int(x), int(y + corner_size))
        return self._create_icon(draw)
    
    def zoom_in(self):
        """放大"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            center_x, center_y = size / 2, size / 2
            # 绘制放大镜
            radius = size * 0.25
            painter.drawEllipse(int(center_x - radius), int(center_y - radius),
                              int(radius * 2), int(radius * 2))
            # 手柄
            handle_len = size * 0.2
            painter.drawLine(int(center_x + radius * 0.7), int(center_y + radius * 0.7),
                           int(center_x + radius * 0.7 + handle_len),
                           int(center_y + radius * 0.7 + handle_len))
            # 加号
            cross_size = size * 0.15
            painter.drawLine(int(center_x), int(center_y - cross_size/2),
                           int(center_x), int(center_y + cross_size/2))
            painter.drawLine(int(center_x - cross_size/2), int(center_y),
                           int(center_x + cross_size/2), int(center_y))
        return self._create_icon(draw)
    
    def zoom_out(self):
        """缩小"""
        def draw(painter, size, color):
            pen = QPen(color, 1.5)
            painter.setPen(pen)
            center_x, center_y = size / 2, size / 2
            # 绘制放大镜
            radius = size * 0.25
            painter.drawEllipse(int(center_x - radius), int(center_y - radius),
                              int(radius * 2), int(radius * 2))
            # 手柄
            handle_len = size * 0.2
            painter.drawLine(int(center_x + radius * 0.7), int(center_y + radius * 0.7),
                           int(center_x + radius * 0.7 + handle_len),
                           int(center_y + radius * 0.7 + handle_len))
            # 减号
            line_len = size * 0.15
            painter.drawLine(int(center_x - line_len/2), int(center_y),
                           int(center_x + line_len/2), int(center_y))
        return self._create_icon(draw)
    
    def help(self):
        """帮助"""
        return self._get_standard_icon(QStyle.SP_MessageBoxQuestion)
    
    def about(self):
        """关于"""
        return self._get_standard_icon(QStyle.SP_MessageBoxInformation)
    
    def exit(self):
        """退出"""
        return self._get_standard_icon(QStyle.SP_DialogCloseButton)
    
    # ========== 应用程序图标 ==========
    def app_icon(self, size=64):
        """
        创建应用程序主图标
        绘制一个专业的 FEM 分析软件图标（立方体+网格）
        """
        def draw(painter, size, color):
            # 背景渐变
            from PyQt5.QtGui import QLinearGradient
            gradient = QLinearGradient(0, 0, size, size)
            gradient.setColorAt(0, QColor(70, 130, 180))  # 钢蓝色
            gradient.setColorAt(1, QColor(30, 80, 120))    # 深蓝色
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(0, 0, size, size, size * 0.15, size * 0.15)
            
            # 绘制立方体（等轴视图）
            margin = size * 0.15
            cube_size = size * 0.5
            center_x, center_y = size / 2, size / 2
            
            # 立方体前面（浅色）
            front_points = [
                QPoint(int(center_x - cube_size/2), int(center_y + cube_size/4)),
                QPoint(int(center_x + cube_size/2), int(center_y + cube_size/4)),
                QPoint(int(center_x + cube_size/2), int(center_y - cube_size/4)),
                QPoint(int(center_x - cube_size/2), int(center_y - cube_size/4)),
            ]
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawPolygon(QPolygon(front_points))
            
            # 立方体顶面（中等亮度）
            top_points = [
                QPoint(int(center_x - cube_size/2), int(center_y - cube_size/4)),
                QPoint(int(center_x + cube_size/2), int(center_y - cube_size/4)),
                QPoint(int(center_x + cube_size/3), int(center_y - cube_size/2)),
                QPoint(int(center_x - cube_size/3), int(center_y - cube_size/2)),
            ]
            painter.setBrush(QBrush(QColor(255, 255, 255, 150)))
            painter.drawPolygon(QPolygon(top_points))
            
            # 立方体右侧面（较暗）
            right_points = [
                QPoint(int(center_x + cube_size/2), int(center_y + cube_size/4)),
                QPoint(int(center_x + cube_size/2), int(center_y - cube_size/4)),
                QPoint(int(center_x + cube_size/3), int(center_y - cube_size/2)),
                QPoint(int(center_x + cube_size/3), int(center_y)),
            ]
            painter.setBrush(QBrush(QColor(255, 255, 255, 100)))
            painter.drawPolygon(QPolygon(right_points))
            
            # 绘制网格线（表示有限元网格）
            painter.setPen(QPen(QColor(100, 150, 200), 1))
            grid_step = cube_size / 3
            # 前面网格
            for i in range(4):
                x = center_x - cube_size/2 + i * grid_step
                painter.drawLine(int(x), int(center_y - cube_size/4), int(x), int(center_y + cube_size/4))
            for i in range(4):
                y = center_y - cube_size/4 + i * grid_step/2
                painter.drawLine(int(center_x - cube_size/2), int(y), int(center_x + cube_size/2), int(y))
        
        return self._create_icon(draw, size=size, color=QColor(70, 130, 180))


# 全局单例实例
icon_manager = IconManager()
