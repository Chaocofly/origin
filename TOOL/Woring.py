import sqlite3
import threading
from datetime import datetime, timedelta

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt

DB_NAME = "robot_alarms.db"
PASSWORD = "hljd1234"

ALARM_FIELDS = [
    "急停状态",
    "碰撞检测",
    "超软限位故障",
    "安全停止信号SIO",
    "安全停止信号SII",
    "主故障码",
    "子故障码"
]

class AlarmLogger:
    def __init__(self):
        self.lock = threading.Lock()
        self.connection = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.create_table()
        self.last_states = {}
        self.cleanup_old_records()

    def create_table(self):
        with self.connection:
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS alarm_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alarm_name TEXT NOT NULL,
                    alarm_value INTEGER,
                    start_time TEXT,
                    end_time TEXT
                )
            """)

    def log_state_change(self, alarm_name, current_value):
        if alarm_name not in ALARM_FIELDS:
            return
        with self.lock:
            prev = self.last_states.get(alarm_name, 0)
            if current_value != prev:
                now = datetime.now().isoformat(timespec="seconds")
                if current_value:
                    # 报警发生
                    self.connection.execute("""
                        INSERT INTO alarm_history (alarm_name, alarm_value, start_time)
                        VALUES (?, ?, ?)
                    """, (alarm_name, 1, now))
                else:
                    # 报警恢复
                    self.connection.execute("""
                        UPDATE alarm_history
                        SET end_time = ?
                        WHERE alarm_name = ? AND end_time IS NULL
                    """, (now, alarm_name))
                self.connection.commit()
            self.last_states[alarm_name] = current_value

    def query_history(self):
        with self.lock:
            cursor = self.connection.execute("""
                SELECT alarm_name, alarm_value, start_time, end_time
                FROM alarm_history
                ORDER BY start_time DESC
            """)
            return cursor.fetchall()

    def cleanup_old_records(self):
        six_months_ago = datetime.now() - timedelta(days=180)
        cutoff = six_months_ago.isoformat(timespec="seconds")
        with self.lock:
            self.connection.execute("""
                DELETE FROM alarm_history
                WHERE start_time < ?
            """, (cutoff,))
            self.connection.commit()

    def close(self):
        self.connection.close()


class AlarmHistoryDialog(QDialog):
    def __init__(self, alarm_logger, parent=None):
        super().__init__(parent)
        self.alarm_logger = alarm_logger

        self.setWindowTitle("历史报警记录查询")
        self.setMinimumSize(700, 500)

        self.layout = QVBoxLayout(self)

        # 顶部密码输入
        pwd_layout = QHBoxLayout()
        pwd_label = QLabel("输入密码:")
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        pwd_layout.addWidget(pwd_label)
        pwd_layout.addWidget(self.pwd_input)
        self.layout.addLayout(pwd_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["报警项目", "出现时间", "恢复时间"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.layout.addWidget(self.table)

        # 按钮区
        btn_layout = QHBoxLayout()
        self.query_button = QPushButton("查询")
        self.query_button.clicked.connect(self.load_records)
        btn_layout.addWidget(self.query_button)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh)
        btn_layout.addWidget(self.refresh_button)

        btn_layout.addStretch()
        self.layout.addLayout(btn_layout)

    def load_records(self):
        password = self.pwd_input.text().strip()
        if password != PASSWORD:
            QMessageBox.warning(self, "错误", "密码错误")
            return

        self.pwd_input.setEnabled(False)
        self.show_records()

    def refresh(self):
        if not self.pwd_input.isEnabled():
            self.show_records()

    def show_records(self):
        records = self.alarm_logger.query_history()

        self.table.setRowCount(0)
        for row_data in records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            alarm_name, alarm_value, start_time, end_time = row_data
            self.table.setItem(row, 0, QTableWidgetItem(alarm_name))
            self.table.setItem(row, 1, QTableWidgetItem(start_time or ""))
            self.table.setItem(row, 2, QTableWidgetItem(end_time or "未恢复"))
