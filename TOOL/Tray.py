# tray_manager.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QGridLayout, QLabel,
    QLineEdit, QPushButton, QMessageBox, QPlainTextEdit
)
from PySide6.QtCore import Signal, Slot, QDateTime
from PySide6.QtGui import QTextCursor


class Tray:
    def __init__(self, name, signal_address):
        self.name = name
        self.signal_address = signal_address
        self.current_count = 0
        self.max_count = 0
        self.active = False  # 默认状态为禁用
        self.last_signal = False
        self.full = False  # 新增：料盘满状态标志

    def reset(self):
        self.current_count = 0


        # 重置后保持当前激活状态（如果之前已启用则保持启用）

    def set_max_count(self, max_count):
        try:
            max_val = int(max_count)
            self.max_count = max_val

            # 关键修改：只有当设置值大于0时才启用料盘
            if max_val > 0:
                self.active = True
                return True
            else:
                self.active = False
                return True  # 返回True表示设置成功，但料盘被禁用
        except ValueError:
            return False

    def process_signal(self, signal_value):
        # 不活动的料盘不处理信号
        if not self.active:
            self.last_signal = signal_value
            return False

        # 检测上升沿（从False变为True）
        if not self.last_signal and signal_value:
            self.current_count += 1

            # 检查是否达到最大值
            if self.current_count >= self.max_count:
                self.active = False
                return True  # 返回True表示料盘已满

        self.last_signal = signal_value
        return False


class TrayManagementTab(QWidget):
    tray_full_signal = Signal(str)  # 信号用于通知哪个料盘已满
    plc_signal_request = Signal(bool)  # 新增：PLC信号请求信号
    reset_signal_request = Signal()  # 新增：复位信号请求信号

    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.main_window = main_window  # 保存主窗口引用
        # 创建两个料盘（默认禁用）
        self.tray1 = Tray("料盘1", "V750.0")
        self.tray2 = Tray("料盘2", "V750.0")
        # 连接PLC信号请求

        self.plc_signal_request.connect(self.send_plc_signal)
        self.reset_signal_request.connect(self.reset_plc_signal)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 料盘1设置
        tray1_group = QGroupBox("料盘1设置")
        tray1_layout = QGridLayout()

        self.tray1_status_label = QLabel("状态: 禁用")  # 状态标签
        tray1_layout.addWidget(self.tray1_status_label, 0, 0, 1, 2)

        self.tray1_count_label = QLabel("当前计数: 0")
        tray1_layout.addWidget(QLabel("当前计数:"), 1, 0)
        tray1_layout.addWidget(self.tray1_count_label, 1, 1)

        tray1_layout.addWidget(QLabel("最大计数:"), 2, 0)
        self.tray1_max_input = QLineEdit("0")
        self.tray1_max_input.setFixedWidth(100)
        tray1_layout.addWidget(self.tray1_max_input, 2, 1)

        self.tray1_set_btn = QPushButton("设置")
        self.tray1_set_btn.clicked.connect(self.set_tray1_max)
        tray1_layout.addWidget(self.tray1_set_btn, 2, 2)

        self.tray1_reset_btn = QPushButton("重置计数")
        self.tray1_reset_btn.clicked.connect(self.reset_tray1)
        tray1_layout.addWidget(self.tray1_reset_btn, 3, 0, 1, 3)

        tray1_group.setLayout(tray1_layout)
        layout.addWidget(tray1_group)

        # 料盘2设置
        tray2_group = QGroupBox("料盘2设置")
        tray2_layout = QGridLayout()

        self.tray2_status_label = QLabel("状态: 禁用")  # 状态标签
        tray2_layout.addWidget(self.tray2_status_label, 0, 0, 1, 2)

        self.tray2_count_label = QLabel("当前计数: 0")
        tray2_layout.addWidget(QLabel("当前计数:"), 1, 0)
        tray2_layout.addWidget(self.tray2_count_label, 1, 1)

        tray2_layout.addWidget(QLabel("最大计数:"), 2, 0)
        self.tray2_max_input = QLineEdit("0")
        self.tray2_max_input.setFixedWidth(100)
        tray2_layout.addWidget(self.tray2_max_input, 2, 1)

        self.tray2_set_btn = QPushButton("设置")
        self.tray2_set_btn.clicked.connect(self.set_tray2_max)
        tray2_layout.addWidget(self.tray2_set_btn, 2, 2)

        self.tray2_reset_btn = QPushButton("重置计数")
        self.tray2_reset_btn.clicked.connect(self.reset_tray2)
        tray2_layout.addWidget(self.tray2_reset_btn, 3, 0, 1, 3)

        tray2_group.setLayout(tray2_layout)
        layout.addWidget(tray2_group)

        # 状态信息 - 修改为日志式显示
        status_group = QGroupBox("状态信息")
        status_layout = QVBoxLayout()

        # 使用QPlainTextEdit代替QLabel，支持多行日志显示
        self.status_text_edit = QPlainTextEdit()
        self.status_text_edit.setReadOnly(True)  # 设置为只读
        self.status_text_edit.setMaximumHeight(150)  # 设置最大高度
        self.status_text_edit.setMinimumHeight(100)  # 设置最小高度
        self.status_text_edit.setPlainText("就绪 - 等待PLC信号")  # 初始文本

        status_layout.addWidget(self.status_text_edit)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        layout.addStretch()

        # 连接料盘满信号
        self.tray_full_signal.connect(self.handle_tray_full)

    def append_status_message(self, message):
        """添加新的状态消息（不覆盖原有内容）"""
        # 获取当前时间
        current_time = QDateTime.currentDateTime().toString("hh:mm:ss")
        # 创建带时间戳的消息
        timestamped_message = f"[{current_time}] {message}"

        # 将消息追加到文本区域
        self.status_text_edit.appendPlainText(timestamped_message)

        # 滚动到底部以显示最新消息
        self.status_text_edit.verticalScrollBar().setValue(
            self.status_text_edit.verticalScrollBar().maximum()
        )

    def set_tray1_max(self):
        if self.tray1.set_max_count(self.tray1_max_input.text()):
            # 发送PLC复位信号
            self.plc_signal_request.emit(False)
            # 更新状态显示
            if self.tray1.active:
                status_text = f"已启用 (最大计数: {self.tray1.max_count})"
                self.append_status_message(f"料盘1已启用，最大计数设置为: {self.tray1.max_count}")
            else:
                status_text = "禁用"
                self.append_status_message("料盘1已禁用 (最大计数为0)")

            self.tray1_status_label.setText(f"状态: {status_text}")
            self.tray1_count_label.setText(f"当前计数: {self.tray1.current_count}")
        else:
            QMessageBox.warning(self, "输入错误", "请输入有效的整数值")

    def set_tray2_max(self):
        if self.tray2.set_max_count(self.tray2_max_input.text()):
            # 发送PLC复位信号
            self.plc_signal_request.emit(False)
            # 更新状态显示
            if self.tray2.active:
                status_text = f"已启用 (最大计数: {self.tray2.max_count})"
                self.append_status_message(f"料盘2已启用，最大计数设置为: {self.tray2.max_count}")
            else:
                status_text = "禁用"
                self.append_status_message("料盘2已禁用 (最大计数为0)")

            self.tray2_status_label.setText(f"状态: {status_text}")
            self.tray2_count_label.setText(f"当前计数: {self.tray2.current_count}")
        else:
            QMessageBox.warning(self, "输入错误", "请输入有效的整数值")

    def reset_tray1(self):
        self.tray1.reset()
        self.tray1_count_label.setText(f"当前计数: {self.tray1.current_count}")

        # 重置后更新状态
        if self.tray1.active:
            self.append_status_message("料盘1计数已重置，料盘已启用")
        else:
            self.append_status_message("料盘1计数已重置，但料盘仍禁用")

    def reset_tray2(self):
        self.tray2.reset()
        self.tray2_count_label.setText(f"当前计数: {self.tray2.current_count}")

        # 重置后更新状态
        if self.tray2.active:
            self.append_status_message("料盘2计数已重置，料盘已启用")
        else:
            self.append_status_message("料盘2计数已重置，但料盘仍禁用")

    @Slot(str)
    def handle_tray_full(self, tray_name):
        # 发送PLC信号请求
        self.plc_signal_request.emit(True)

        # 显示弹窗
        msg_box = QMessageBox()
        msg_box.setWindowTitle("料盘已满")
        msg_box.setText(f"{tray_name} 已达到设定数量！请更换料盘并重置计数。")
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.buttonClicked.connect(self.on_msg_box_clicked)  # 连接按钮点击信号
        msg_box.exec()

        self.append_status_message(f"{tray_name} 已满！")

        # 更新状态标签
        if tray_name == "料盘1":
            self.tray1_status_label.setText("状态: 已满")
        else:
            self.tray2_status_label.setText("状态: 已满")

    def process_signal(self, signal_value):
        # 处理料盘1信号 - 只有active的料盘才会处理信号
        if self.tray1.active:
            if self.tray1.process_signal(signal_value):
                self.tray_full_signal.emit(self.tray1.name)
            self.tray1_count_label.setText(f"当前计数: {self.tray1.current_count}")
            self.tray1_status_label.setText(f"状态: 计数中 ({self.tray1.current_count}/{self.tray1.max_count})")

        # 处理料盘2信号 - 只有active的料盘才会处理信号
        if self.tray2.active:
            if self.tray2.process_signal(signal_value):
                self.tray_full_signal.emit(self.tray2.name)
            self.tray2_count_label.setText(f"当前计数: {self.tray2.current_count}")
            self.tray2_status_label.setText(f"状态: 计数中 ({self.tray2.current_count}/{self.tray2.max_count})")

    @Slot()
    def on_msg_box_clicked(self, button):
        """当用户点击消息框按钮时调用"""
        # 用户点击确定按钮后复位PLC信号
        self.reset_signal_request.emit()

    @Slot()
    def reset_plc_signal(self):
        """复位PLC信号"""
        # 发送复位信号
        self.plc_signal_request.emit(False)
        self.append_status_message("复位 PLC 信号: V750.0 = False")

    @Slot(bool)
    def send_plc_signal(self, value):
        """发送PLC V750.7信号"""
        if self.main_window:
            self.main_window.set_750_7_signal(value)
            status = "True" if value else "False"
            self.append_status_message(f"发送 PLC 信号: V750.7 = {status}")