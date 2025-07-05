# control_panel.py
from PySide6.QtWidgets import (QWidget, QPushButton, QGridLayout, QGroupBox,
                               QVBoxLayout, QLabel, QApplication)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
import snap7


class ControlPanelTab(QWidget):
    def __init__(self, plc_ip='192.168.58.10', parent=None):
        super().__init__(parent)
        self.plc_ip = plc_ip
        self.button_states = {
            "pause": False,
            "resume": False,
            "stop": False,
            "start": False,
            "home": False,
            "auto_manual": False,
            "gripper1": False,  # 新增手爪1使能
            "gripper2": False,  # 新增手爪2使能
            "blow": False  # 新增吹气使能
        }
        self.manual_mode = False  # 手动模式状态
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("机器人控制面板")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50; padding: 10px;")
        main_layout.addWidget(title_label)

        # 控制按钮组
        control_group = QGroupBox("控制命令")
        control_layout = QGridLayout(control_group)

        # 按钮定义 - 原有按钮
        self.buttons = {
            "pause": QPushButton("暂停"),
            "resume": QPushButton("恢复"),
            "stop": QPushButton("停止"),
            "start": QPushButton("启动"),
            "home": QPushButton("回工作原点"),
            "auto_manual": QPushButton("手自动切换"),
            # 新增的三个按钮
            "gripper1": QPushButton("原料手爪"),
            "gripper2": QPushButton("成品手爪"),
            "blow": QPushButton("吹气功能")
        }

        # 设置按钮样式并连接信号
        for key, btn in self.buttons.items():
            btn.setFixedHeight(50)
            btn.setFont(QFont("Arial", 12))

            # 为停止按钮设置特殊样式
            if key == "stop":
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;  /* 红色 */
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;  /* 深红色 */
                    }
                    QPushButton:pressed {
                        background-color: #922b21;  /* 更深的红色 */
                    }
                """)
            # 为新增按钮设置不同颜色
            elif key in ["gripper1", "gripper2"]:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;  /* 蓝色 */
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                    QPushButton:pressed {
                        background-color: #1c6ea4;
                    }
                    QPushButton:disabled {
                        background-color: #bdc3c7;  /* 灰色 */
                    }
                """)
            elif key == "blow":
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f39c12;  /* 橙色 */
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #e67e22;
                    }
                    QPushButton:pressed {
                        background-color: #d35400;
                    }
                    QPushButton:disabled {
                        background-color: #bdc3c7;  /* 灰色 */
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;  /* 蓝色 */
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                    QPushButton:pressed {
                        background-color: #1c6ea4;
                    }
                """)

            # 为三个新增按钮连接不同的信号（修复lambda参数问题）
            if key in ["gripper1", "gripper2", "blow"]:
                # 修复：使用无参数的lambda表达式
                btn.pressed.connect(lambda k=key: self.activate_gripper_button(k, True))
                btn.released.connect(lambda k=key: self.activate_gripper_button(k, False))
            else:
                btn.clicked.connect(lambda checked, k=key: self.activate_button(k))

        # 布局按钮 - 原有布局
        control_layout.addWidget(self.buttons["pause"], 0, 0)
        control_layout.addWidget(self.buttons["resume"], 0, 1)
        control_layout.addWidget(self.buttons["start"], 0, 2)
        control_layout.addWidget(self.buttons["stop"], 1, 0)
        control_layout.addWidget(self.buttons["home"], 1, 1)
        control_layout.addWidget(self.buttons["auto_manual"], 1, 2)

        # 新增按钮布局 - 第三行
        control_layout.addWidget(self.buttons["gripper1"], 2, 0)
        control_layout.addWidget(self.buttons["gripper2"], 2, 1)
        control_layout.addWidget(self.buttons["blow"], 2, 2)

        # 状态显示
        status_group = QGroupBox("当前状态")
        status_layout = QGridLayout(status_group)

        self.status_labels = {
            "pause": QLabel("暂停: OFF"),
            "resume": QLabel("恢复: OFF"),
            "stop": QLabel("停止: OFF"),
            "start": QLabel("启动: OFF"),
            "home": QLabel("回原点: OFF"),
            "auto_manual": QLabel("自动模式: OFF"),
            # 新增状态标签
            "gripper1": QLabel("原料手爪: OFF"),
            "gripper2": QLabel("成品手爪: OFF"),
            "blow": QLabel("吹气功能: OFF")
        }

        # 设置布局 - 3列布局
        row, col = 0, 0
        for key, label in self.status_labels.items():
            label.setFont(QFont("Arial", 11))
            label.setAlignment(Qt.AlignCenter)
            status_layout.addWidget(label, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

        # 添加控件到主布局
        main_layout.addWidget(control_group)
        main_layout.addWidget(status_group)
        main_layout.addStretch()

        # 初始设置新增按钮状态
        self.update_button_availability()

    def set_manual_mode(self, is_manual):
        """设置手动模式状态并更新按钮可用性"""
        self.manual_mode = is_manual
        self.update_button_availability()

    def update_button_availability(self):
        """根据手动模式状态更新按钮可用性"""
        self.buttons["gripper1"].setEnabled(self.manual_mode)
        self.buttons["gripper2"].setEnabled(self.manual_mode)
        self.buttons["blow"].setEnabled(self.manual_mode)

        # 更新状态标签提示
        if not self.manual_mode:
            self.status_labels["gripper1"].setText("原料手爪: (自动模式禁用)")
            self.status_labels["gripper2"].setText("成品手爪: (自动模式禁用)")
            self.status_labels["blow"].setText("吹气功能: (自动模式禁用)")
            # 设置灰色提示
            for label in [self.status_labels["gripper1"],
                          self.status_labels["gripper2"],
                          self.status_labels["blow"]]:
                label.setStyleSheet("color: gray;")
        else:
            # 恢复默认显示
            self.update_button_ui("gripper1", self.button_states["gripper1"])
            self.update_button_ui("gripper2", self.button_states["gripper2"])
            self.update_button_ui("blow", self.button_states["blow"])

    def activate_button(self, button_key):
        """激活按钮并写入PLC（用于原有按钮）"""
        # 更新状态为True
        self.button_states[button_key] = True
        self.update_button_ui(button_key, True)

        # 写入PLC
        self.write_to_plc(button_key, True)

        # 设置定时器在1秒后复位按钮
        QTimer.singleShot(300, lambda: self.reset_button(button_key))

    def reset_button(self, button_key):
        """复位按钮状态（用于原有按钮）"""
        self.button_states[button_key] = False
        self.update_button_ui(button_key, False)
        self.write_to_plc(button_key, False)

    def activate_gripper_button(self, button_key, state):
        """处理新增按钮的按下/释放（按1松0）"""
        # 如果是新增按钮且不在手动模式，则忽略
        if not self.manual_mode:
            return

        # 更新状态
        self.button_states[button_key] = state
        self.update_button_ui(button_key, state)

        # 写入PLC
        self.write_to_plc(button_key, state)

    def update_button_ui(self, button_key, state):
        """更新按钮和状态标签的UI"""
        btn = self.buttons[button_key]
        label = self.status_labels[button_key]

        # 为停止按钮设置特殊样式
        if button_key == "stop":
            if state:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ff6b6b;  /* 亮红色 */
                        color: white;
                        border-radius: 5px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;  /* 标准红色 */
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;  /* 深红色 */
                    }
                    QPushButton:pressed {
                        background-color: #922b21;  /* 更深的红色 */
                    }
                """)
        # 为新增按钮设置样式
        elif button_key in ["gripper1", "gripper2"]:
            if state:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2ecc71;  /* 绿色 */
                        color: white;
                        border-radius: 5px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;  /* 蓝色 */
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #2980b9;
                    }
                    QPushButton:pressed {
                        background-color: #1c6ea4;
                    }
                    QPushButton:disabled {
                        background-color: #bdc3c7;  /* 灰色 */
                    }
                """)
        elif button_key == "blow":
            if state:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2ecc71;  /* 绿色 */
                        color: white;
                        border-radius: 5px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #f39c12;  /* 橙色 */
                        color: white;
                        border-radius: 5px;
                    }
                    QPushButton:hover {
                        background-color: #e67e22;
                    }
                    QPushButton:pressed {
                        background-color: #d35400;
                    }
                    QPushButton:disabled {
                        background-color: #bdc3c7;  /* 灰色 */
                    }
                """)
        else:
            if state:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2ecc71;  /* 绿色 */
                        color: white;
                        border-radius: 5px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3498db;  /* 蓝色 */
                        color: white;
                        border-radius: 5px;
                    }
                """)

        # 更新状态标签
        status_text = {
            "pause": f"暂停: {'ON' if state else 'OFF'}",
            "resume": f"恢复: {'ON' if state else 'OFF'}",
            "stop": f"停止: {'ON' if state else 'OFF'}",
            "start": f"启动: {'ON' if state else 'OFF'}",
            "home": f"回原点: {'ON' if state else 'OFF'}",
            "auto_manual": f"自动模式: {'ON' if state else 'OFF'}",
            "gripper1": f"原料手爪: {'ON' if state else 'OFF'}",
            "gripper2": f"成品手爪: {'ON' if state else 'OFF'}",
            "blow": f"吹气功能: {'ON' if state else 'OFF'}"
        }

        # 特殊处理自动模式下的显示
        if button_key in ["gripper1", "gripper2", "blow"] and not self.manual_mode:
            label.setText(f"{status_text[button_key]} (自动模式禁用)")
            label.setStyleSheet("color: gray;")
        else:
            label.setText(status_text[button_key])
            # 高亮显示状态
            if state:
                label.setStyleSheet("color: green; font-weight: bold;")
            else:
                label.setStyleSheet("color: black; font-weight: normal;")

    def write_to_plc(self, button_key, value):
        """向PLC写入数据"""
        # 地址映射 - 新增三个按钮的地址
        address_map = {
            "pause": ("V400.0", 400, 0),
            "resume": ("V400.1", 400, 1),
            "start": ("V400.2", 400, 2),
            "stop": ("V400.3", 400, 3),
            "home": ("V400.4", 400, 4),
            "auto_manual": ("V400.5", 400, 5),
            "gripper1": ("V300.0", 300, 0),  # 手爪1使能
            "gripper2": ("V300.1", 300, 1),  # 手爪2使能
            "blow": ("V300.2", 300, 2)  # 吹气使能
        }

        address_name, byte_addr, bit = address_map[button_key]

        try:
            plc = snap7.client.Client()
            plc.connect(self.plc_ip, 0, 1)

            if plc.get_connected():
                # 读取当前字节值
                data = plc.db_read(1, byte_addr, 1)
                current_byte = data[0]

                # 更新特定位
                if value:
                    new_byte = current_byte | (1 << bit)
                else:
                    new_byte = current_byte & ~(1 << bit)

                # 写入新值
                plc.db_write(1, byte_addr, bytearray([new_byte]))

            plc.disconnect()
        except Exception as e:
            print(f"PLC写入错误: {str(e)}")

    def set_plc_ip(self, ip_address):
        """设置PLC IP地址"""
        self.plc_ip = ip_address