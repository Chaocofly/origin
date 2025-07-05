# Tool2.py
import sqlite3
from datetime import datetime

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
    QMessageBox, QLabel, QInputDialog, QComboBox
)
from PySide6.QtCore import Qt


class ToolChangeDialog2(QDialog):
    def __init__(self, tool_id, parent=None, db_path=None):
        super().__init__(parent)
        self.setWindowTitle(f"刀具 {tool_id} 寿命到期")
        self.setFixedSize(400, 300)
        self.db_path = db_path

        layout = QVBoxLayout()

        title = QLabel(f"刀具 {tool_id} 已达到使用寿命，请更换！")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #d32f2f;")
        layout.addWidget(title)

        form_layout = QFormLayout()

        self.new_life_input = QLineEdit()
        self.new_life_input.setPlaceholderText("输入新的寿命设定值")
        form_layout.addRow("新的寿命设定值:", self.new_life_input)

        self.change_reason_combo = QComboBox()
        self.change_reason_combo.setEditable(True)
        self.load_change_reason_history()
        form_layout.addRow("更换原因:", self.change_reason_combo)

        self.operator_combo = QComboBox()
        self.operator_combo.setEditable(True)
        self.load_operator_history()
        form_layout.addRow("操作员:", self.operator_combo)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def load_change_reason_history(self):
        if not self.db_path:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT reason FROM change_reason_history ORDER BY reason")
        reasons = [row[0] for row in cursor.fetchall()]
        conn.close()
        self.change_reason_combo.addItems(reasons)

    def load_operator_history(self):
        if not self.db_path:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT operator FROM operator_history ORDER BY operator")
        operators = [row[0] for row in cursor.fetchall()]
        conn.close()
        self.operator_combo.addItems(operators)

    def get_values(self):
        return {
            "new_life": self.new_life_input.text(),
            "reason": self.change_reason_combo.currentText(),
            "operator": self.operator_combo.currentText()
        }


class ToolHistoryDialog2(QDialog):
    def __init__(self, tool_id, db_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"刀具 {tool_id} 更换历史")
        self.setFixedSize(800, 600)
        self.db_path = db_path
        self.tool_id = tool_id

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # 创建表格
        self.table = QTableWidget()
        self.layout.addWidget(self.table)

        # 清除历史按钮（只在查看所有历史时显示）
        if tool_id == "*":
            clear_btn = QPushButton("清除所有历史记录")
            clear_btn.setFixedHeight(30)
            clear_btn.clicked.connect(self.clear_history)
            self.layout.addWidget(clear_btn)

        self.load_data()

    def load_data(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if self.tool_id == "*":
            cursor.execute("""
                SELECT tool_id, start_time, end_time, change_reason, new_life_setting, operator 
                FROM tool_history 
                ORDER BY end_time DESC
            """)
            records = cursor.fetchall()
            column_labels = ["刀具ID", "开始时间", "结束时间", "更换原因", "新设定寿命", "操作员"]
        else:
            cursor.execute("""
                SELECT start_time, end_time, change_reason, new_life_setting, operator 
                FROM tool_history 
                WHERE tool_id = ?
                ORDER BY end_time DESC
            """, (self.tool_id,))
            records = cursor.fetchall()
            column_labels = ["开始时间", "结束时间", "更换原因", "新设定寿命", "操作员"]

        conn.close()

        self.table.clear()
        self.table.setRowCount(len(records))
        self.table.setColumnCount(len(column_labels))
        self.table.setHorizontalHeaderLabels(column_labels)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for row_idx, row_data in enumerate(records):
            for col_idx, col_data in enumerate(row_data):
                item = QTableWidgetItem(str(col_data))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_idx, col_idx, item)

    def clear_history(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tool_history")
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            QMessageBox.information(self, "提示", "没有历史记录可以清除。")
            return

        password, ok = QInputDialog.getText(self, "请输入密码", "密码:", QLineEdit.Password)
        if ok:
            if password == "123456":
                reply = QMessageBox.question(
                    self,
                    "确认清除",
                    "确认清除所有刀具历史记录吗？此操作不可恢复！",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tool_history")
                    conn.commit()
                    conn.close()

                    QMessageBox.information(self, "成功", "历史记录已清除。")
                    self.load_data()
            else:
                QMessageBox.warning(self, "密码错误", "密码错误，无法清除历史记录。")


class ToolManager2:
    def __init__(self, plc_callback=None, db_path="tool_history2.db"):
        self.db_path = db_path
        self.tools = []
        self.current_counts = {}
        self.life_settings = {}
        self.db_setup()
        self.init_tools()
        self.plc_callback = plc_callback  # 保存回调函数

    def db_setup(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                change_reason TEXT,
                new_life_setting INTEGER NOT NULL,
                operator TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS change_reason_history (
                reason TEXT PRIMARY KEY
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS operator_history (
                operator TEXT PRIMARY KEY
            )
        """)
        conn.commit()
        conn.close()

    def init_tools(self):
        # 初始化24把刀具
        for i in range(24):
            tool_id = f"T{i}"
            self.tools.append(tool_id)
            # 默认寿命设定为0，表示不计数
            self.life_settings[tool_id] = 0
            self.current_counts[tool_id] = 0

    def record_tool_change(self, tool_id, start_time, end_time, change_reason, new_life_setting, operator):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tool_history (tool_id, start_time, end_time, change_reason, new_life_setting, operator)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tool_id, start_time, end_time, change_reason, new_life_setting, operator))
        conn.commit()
        conn.close()

    def save_history_record(self, reason, operator):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO change_reason_history(reason) VALUES(?)", (reason,))
        cursor.execute("INSERT OR IGNORE INTO operator_history(operator) VALUES(?)", (operator,))
        conn.commit()
        conn.close()

    def check_tool_life(self, tool_id, parent_widget=None):
        if self.life_settings.get(tool_id, 0) <= 0:
            return True

        if self.current_counts[tool_id] >= self.life_settings[tool_id]:
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 发送 PLC 信号 - V600.7 = True
            if self.plc_callback:
                self.plc_callback(True)

            dialog = ToolChangeDialog2(tool_id, parent_widget, self.db_path)
            if dialog.exec() == QDialog.Accepted:
                values = dialog.get_values()
                try:
                    new_life = int(values["new_life"])
                    reason = values["reason"]
                    operator = values["operator"]

                    self.save_history_record(reason, operator)

                    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.record_tool_change(
                        tool_id, start_time, end_time, reason, new_life, operator
                    )

                    self.current_counts[tool_id] = 0
                    self.life_settings[tool_id] = new_life

                    # 复位 PLC 信号 - V600.7 = False
                    if self.plc_callback:
                        self.plc_callback(False)
                    return True
                except ValueError:
                    QMessageBox.warning(parent_widget, "输入错误", "寿命设定值必须是整数")
                    # 复位 PLC 信号
                    if self.plc_callback:
                        self.plc_callback(False)
                    return False
            else:
                # 用户取消 - 复位 PLC 信号
                if self.plc_callback:
                    self.plc_callback(False)
                return False
        return True


class ToolManagementTab2(QWidget):
    def __init__(self, tool_manager, parent=None):
        super().__init__(parent)
        self.tool_manager = tool_manager
        self.last_signal_state = False
        self.shown_dialogs = set()
        self.open_dialogs = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        title = QLabel("刀具管理系统2")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2c3e50;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setRowCount(len(self.tool_manager.tools))
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["刀具型号", "设定寿命", "当前计数", "操作"])

        for row, tool_id in enumerate(self.tool_manager.tools):
            tool_item = QTableWidgetItem(tool_id)
            tool_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, tool_item)

            life_item = QTableWidgetItem(str(self.tool_manager.life_settings[tool_id]))
            life_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, life_item)

            count_item = QTableWidgetItem(str(self.tool_manager.current_counts[tool_id]))
            count_item.setTextAlignment(Qt.AlignCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, count_item)

            edit_btn = QPushButton("修改设定")
            edit_btn.setFixedSize(80, 25)
            edit_btn.clicked.connect(lambda _, t=tool_id: self.edit_tool_setting(t))
            self.table.setCellWidget(row, 3, edit_btn)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: 1px solid #388E3C;
                    border-radius: 5px;
                    padding: 2px 6px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #45A049;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
            """)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        history_all_btn = QPushButton("查看所有刀具更换历史")
        history_all_btn.setFixedHeight(30)
        history_all_btn.clicked.connect(self.show_all_tool_history)
        layout.addWidget(history_all_btn)

        self.setLayout(layout)

    def show_all_tool_history(self):
        dialog = ToolHistoryDialog2("*", self.tool_manager.db_path, self)
        dialog.exec()

    def edit_tool_setting(self, tool_id):
        new_setting, ok = QInputDialog.getInt(
            self,
            f"修改 {tool_id} 寿命设定",
            "输入新的寿命设定值:",
            self.tool_manager.life_settings[tool_id],
            0,
            1000000,
            1
        )
        if ok:
            self.tool_manager.life_settings[tool_id] = new_setting
            self.update_table()
            # 清零所有刀具的当前计数
            self.reset_all_current_counts()

    def update_table(self):
        for row in range(self.table.rowCount()):
            tool_id = self.table.item(row, 0).text()
            self.table.item(row, 1).setText(str(self.tool_manager.life_settings[tool_id]))
            self.table.item(row, 2).setText(str(self.tool_manager.current_counts[tool_id]))

            if self.tool_manager.life_settings[tool_id] <= 0:
                self.table.item(row, 2).setBackground(QColor(220, 220, 220))  # 灰色，表示不计数
                continue

            progress = self.tool_manager.current_counts[tool_id] / self.tool_manager.life_settings[tool_id]
            if progress > 0.9:
                self.table.item(row, 2).setBackground(QColor(255, 200, 200))
            elif progress > 0.7:
                self.table.item(row, 2).setBackground(QColor(255, 255, 200))
            else:
                self.table.item(row, 2).setBackground(QColor(200, 255, 200))

    def reset_all_current_counts(self):
        """重置所有刀具的当前计数为0"""
        for tool in self.tool_manager.tools:
            self.tool_manager.current_counts[tool] = 0
        self.update_table()  # 更新表格显示

    def process_signal(self, signal_state):
        if signal_state and not self.last_signal_state:
            for tool_id in self.tool_manager.tools:
                if self.tool_manager.life_settings[tool_id] <= 0:
                    continue

                # 如果刀具寿命已达到上限且未处理，则跳过计数
                if (tool_id in self.shown_dialogs and
                    self.tool_manager.current_counts[tool_id] >= self.tool_manager.life_settings[tool_id]):
                    continue

                self.tool_manager.current_counts[tool_id] += 1

                if self.tool_manager.current_counts[tool_id] >= self.tool_manager.life_settings[tool_id]:
                    self.shown_dialogs.add(tool_id)

                    if self.tool_manager.check_tool_life(tool_id, self):
                        self.tool_manager.current_counts[tool_id] = 0
                        self.shown_dialogs.discard(tool_id)
                    else:
                        # 用户取消则冻结计数不变
                        pass

        self.last_signal_state = signal_state
        self.update_table()