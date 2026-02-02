import numpy as np
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                             QLabel, QProgressBar, QPushButton, QTabWidget, QWidget, QMessageBox)
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtGui import QFont

# 尝试导入 matplotlib，如果失败则只显示文本，不报错
try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

class JobMonitorDialog(QDialog):
    """
    作业监控窗口
    功能：
    1. 实时绘制残差收敛曲线 (Matplotlib)
    2. 实时显示求解日志
    3. 进度条与状态显示
    4. 终止作业 (Kill)
    """
    def __init__(self, parent=None, job_name="Job-1"):
        super().__init__(parent)
        self.setWindowTitle(f"Job Monitor - {job_name}")
        self.resize(900, 600)
        self.job_name = job_name
        self.is_running = True
        
        # 数据存储 (用于绘图)
        self.iterations = [] # 累计迭代次数
        self.residuals = []  # 残差值 (log10)
        self.total_iter_count = 0
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 顶部状态栏
        top_layout = QHBoxLayout()
        self.lbl_status = QLabel("Status: Running...")
        self.lbl_status.setFont(QFont("Segoe UI", 10, QFont.Bold))
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        
        top_layout.addWidget(self.lbl_status)
        top_layout.addWidget(self.progress_bar, 1)  # 进度条占据剩余空间
        layout.addLayout(top_layout)
        
        # 2. 中间选项卡 (Monitor | Log)
        self.tabs = QTabWidget()
        
        # Tab 1: Convergence Plot (收敛曲线)
        self.tab_plot = QWidget()
        plot_layout = QVBoxLayout(self.tab_plot)
        
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(5, 4), dpi=100)
            # 设置绘图风格
            self.canvas = FigureCanvas(self.figure)
            self.ax = self.figure.add_subplot(111)
            self.ax.set_title("Convergence History")
            self.ax.set_xlabel("Iteration")
            self.ax.set_ylabel("Force Residual (Log10)")
            self.ax.grid(True, linestyle='--', alpha=0.6)
            # 初始化一条空曲线
            self.line, = self.ax.plot([], [], 'b.-', linewidth=1.5, markersize=8)
            plot_layout.addWidget(self.canvas)
        else:
            lbl = QLabel("Matplotlib not found. Plotting disabled.\n(Only text log available)")
            lbl.setAlignment(Qt.AlignCenter)
            plot_layout.addWidget(lbl)
            
        self.tabs.addTab(self.tab_plot, "Monitor")
        
        # Tab 2: Log (文本日志)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Courier New", 9)) # 等宽字体
        self.txt_log.setStyleSheet("background-color: #f0f0f0;")
        self.tabs.addTab(self.txt_log, "Log / Messages")
        
        layout.addWidget(self.tabs)
        
        # 3. 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_stop = QPushButton("Kill Job")
        self.btn_stop.setStyleSheet("background-color: #ffcccc; color: red; font-weight: bold;")
        self.btn_stop.clicked.connect(self.kill_job)
        btn_layout.addWidget(self.btn_stop)
        
        self.btn_close = QPushButton("Dismiss")
        self.btn_close.clicked.connect(self.accept) # 仅关闭窗口，不影响后台
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)

    @pyqtSlot(dict)
    def update_status(self, data):
        """
        接收 Worker 发来的状态数据并更新界面
        data format: {time, dt, iter, residual, converged, increment}
        """
        if not self.is_running: 
            return
        
        if not data:
            return

        # 1. 更新状态文字
        increment = data.get('increment', 0)
        time_val = data.get('time', 0.0)
        iter_val = data.get('iter', 0)
        info = f"Increment: {increment} | Time: {time_val:.4f} | Iteration: {iter_val}"
        if data.get('converged', False):
            info += " [Converged]"
        self.lbl_status.setText(f"Status: {info}")

        # 2. 更新绘图数据
        res = data.get('residual', 0.0)
        self.total_iter_count += 1
        
        if res > 0:
            val = np.log10(res)
        else:
            val = -20 # 避免 log(0)
            
        self.iterations.append(self.total_iter_count)
        self.residuals.append(val)
        
        # 3. 刷新图表（至少需要2个点才能绘制）
        if MATPLOTLIB_AVAILABLE and len(self.iterations) > 1:
            self.line.set_data(self.iterations, self.residuals)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw()

    @pyqtSlot(str)
    def append_log(self, msg):
        """追加日志文本"""
        self.txt_log.append(msg)
        # 自动滚动到底部
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(int)
    def update_progress(self, val):
        """更新进度条"""
        self.progress_bar.setValue(val)
        if val >= 100:
            self.lbl_status.setText("Status: Completed")
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText("Finished")
            self.is_running = False

    def kill_job(self):
        """用户点击终止按钮"""
        if self.is_running:
            reply = QMessageBox.question(
                self, 
                "Kill Job", 
                "Are you sure you want to terminate the current job?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.txt_log.append("\n*** KILL REQUESTED BY USER ***\n")
                # 发送信号给主窗口去停止 worker
                if self.parent() and hasattr(self.parent(), 'stop_solver'):
                    self.parent().stop_solver()
                
                self.lbl_status.setText("Status: Aborted by User")
                self.btn_stop.setEnabled(False)
                self.btn_stop.setText("Aborted")
                self.is_running = False
    
    def restore_from_history(self, history_data):
        """从历史数据恢复监控窗口显示"""
        if not history_data:
            return
        
        # 恢复日志
        if 'log_messages' in history_data:
            for msg in history_data['log_messages']:
                self.txt_log.append(msg)
        
        # 恢复进度
        if 'progress' in history_data:
            self.update_progress(history_data['progress'])
        
        # 恢复迭代和残差数据
        if 'iterations' in history_data and 'residuals' in history_data:
            iterations = history_data['iterations']
            residuals = history_data['residuals']
            
            if iterations and residuals and len(iterations) == len(residuals):
                self.iterations = list(iterations)  # 复制列表
                # 将残差转换为 log10
                self.residuals = []
                for res in residuals:
                    if res > 0:
                        self.residuals.append(np.log10(res))
                    else:
                        self.residuals.append(-20)
                self.total_iter_count = len(self.iterations)
                
                # 恢复图表
                if MATPLOTLIB_AVAILABLE and len(self.iterations) > 0:
                    self.line.set_data(self.iterations, self.residuals)
                    self.ax.relim()
                    self.ax.autoscale_view()
                    self.canvas.draw()
        
        # 恢复最后的状态
        if 'status_history' in history_data and len(history_data['status_history']) > 0:
            last_status = history_data['status_history'][-1]
            increment = last_status.get('increment', 0)
            time_val = last_status.get('time', 0.0)
            iter_val = last_status.get('iter', 0)
            info = f"Increment: {increment} | Time: {time_val:.4f} | Iteration: {iter_val}"
            if last_status.get('converged', False):
                info += " [Converged]"
            self.lbl_status.setText(f"Status: {info}")
    
    def set_completed(self):
        """设置为已完成状态"""
        self.is_running = False
        self.lbl_status.setText("Status: Completed")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setText("Finished")