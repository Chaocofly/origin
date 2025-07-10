import sqlite3
import threading
from datetime import datetime, timedelta

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QLabel, QDateEdit,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QComboBox, QGroupBox
)
from PySide6.QtCore import Qt, QDate

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

    def query_history(self, start_date=None, end_date=None, alarm_name=None):
        """查询历史报警记录，支持日期范围和报警类型过滤"""
        with self.lock:
            # 构建查询条件和参数
            conditions = []
            params = []

            # 添加日期范围条件
            if start_date:
                start_datetime = datetime.combine(start_date, datetime.min.time())
                conditions.append("start_time >= ?")
                params.append(start_datetime.isoformat(timespec="seconds"))
            if end_date:
                end_datetime = datetime.combine(end_date + timedelta(days=1), datetime.min.time())
                conditions.append("start_time < ?")
                params.append(end_datetime.isoformat(timespec="seconds"))

            # 添加报警类型条件
            if alarm_name and alarm_name != "所有类型":
                conditions.append("alarm_name = ?")
                params.append(alarm_name)

            # 构建WHERE子句
            where_clause = " AND ".join(conditions) if conditions else "1"

            # 执行查询
            query = f"""
                SELECT alarm_name, alarm_value, start_time, end_time
                FROM alarm_history
                WHERE {where_clause}
                ORDER BY start_time DESC
            """
            cursor = self.connection.execute(query, tuple(params))
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
        self.authenticated = False  # 标记用户是否已通过密码验证

        self.setWindowTitle("历史报警记录查询")
        self.setMinimumSize(800, 600)

        self.layout = QVBoxLayout(self)

        # 顶部密码输入
        pwd_layout = QHBoxLayout()
        pwd_label = QLabel("输入密码:")
        self.pwd_input = QLineEdit()
        self.pwd_input.setEchoMode(QLineEdit.Password)
        pwd_layout.addWidget(pwd_label)
        pwd_layout.addWidget(self.pwd_input)
        self.layout.addLayout(pwd_layout)

        # 过滤条件区域
        filter_group = QGroupBox("查询条件")
        filter_layout = QFormLayout()

        # 日期范围选择
        start_label = QLabel("开始日期:")
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))  # 默认一个月前

        end_label = QLabel("结束日期:")
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())  # 默认今天

        filter_layout.addRow(start_label, self.start_date_edit)
        filter_layout.addRow(end_label, self.end_date_edit)

        # 报警类型选择
        alarm_label = QLabel("报警类型:")
        self.alarm_combo = QComboBox()
        self.alarm_combo.addItem("所有类型")
        for alarm in ALARM_FIELDS:
            self.alarm_combo.addItem(alarm)

        filter_layout.addRow(alarm_label, self.alarm_combo)

        filter_group.setLayout(filter_layout)
        self.layout.addWidget(filter_group)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["报警项目", "状态", "出现时间", "恢复时间"])
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

        self.clear_button = QPushButton("清除筛选")
        self.clear_button.clicked.connect(self.clear_filters)
        btn_layout.addWidget(self.clear_button)

        btn_layout.addStretch()
        self.layout.addLayout(btn_layout)

    def load_records(self):
        if not self.authenticated:
            # 验证密码
            password = self.pwd_input.text().strip()
            if password != PASSWORD:
                QMessageBox.warning(self, "错误", "密码错误")
                return
            self.authenticated = True
            self.pwd_input.setEnabled(False)  # 验证通过后禁用密码输入

        # 获取过滤条件
        start_date = self.start_date_edit.date().toPython()
        end_date = self.end_date_edit.date().toPython()
        alarm_name = self.alarm_combo.currentText()

        # 查询记录
        records = self.alarm_logger.query_history(
            start_date=start_date,
            end_date=end_date,
            alarm_name=alarm_name
        )

        # 显示记录
        self.show_records(records)

    def refresh(self):
        if self.authenticated:
            self.load_records()

    def clear_filters(self):
        """清除筛选条件"""
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.end_date_edit.setDate(QDate.currentDate())
        self.alarm_combo.setCurrentIndex(0)
        if self.authenticated:
            self.load_records()

    def show_records(self, records):
        self.table.setRowCount(0)
        for row_data in records:
            row = self.table.rowCount()
            self.table.insertRow(row)

            alarm_name, alarm_value, start_time, end_time = row_data

            # 报警项目
            self.table.setItem(row, 0, QTableWidgetItem(alarm_name))

            # 状态 (根据报警值显示)
            status_item = QTableWidgetItem()
            if alarm_value:
                status_item.setText("报警中" if end_time is None else "已恢复")
                status_item.setBackground(QColor(255, 200, 200))  # 浅红色背景
            else:
                status_item.setText("正常")
                status_item.setBackground(QColor(200, 255, 200))  # 浅绿色背景
            self.table.setItem(row, 1, status_item)

            # 时间
            self.table.setItem(row, 2, QTableWidgetItem(start_time or ""))
            self.table.setItem(row, 3, QTableWidgetItem(end_time or "未恢复"))