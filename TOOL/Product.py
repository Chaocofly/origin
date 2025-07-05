# product_statistics.py
import sqlite3
import os
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
                               QHeaderView, QHBoxLayout, QPushButton, QComboBox, QMessageBox,
                               QLineEdit, QGroupBox, QDialog)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont


class ProductStatisticsTab(QWidget):
    def __init__(self, db_path='production_statistics.db'):
        super().__init__()
        self.db_path = db_path
        self.init_db()
        self.init_ui()
        self.update_daily_count()
        self.last_signal = False  # 添加信号状态跟踪

        # 设置定时器检查日期变更
        self.date_check_timer = QTimer(self)
        self.date_check_timer.timeout.connect(self.check_date_change)
        self.date_check_timer.start(60000)  # 每分钟检查一次

    def init_db(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS production_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                count INTEGER NOT NULL
            )
        ''')
        self.conn.commit()

    def init_ui(self):
        layout = QVBoxLayout()

        # 当日生产统计
        self.daily_count_label = QLabel("今日加工数量: 0")
        self.daily_count_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.daily_count_label.setAlignment(Qt.AlignCenter)
        self.daily_count_label.setStyleSheet("color: #2c3e50; padding: 15px;")
        layout.addWidget(self.daily_count_label)

        # 历史记录查询区域
        history_group = QGroupBox("历史记录查询")
        history_layout = QVBoxLayout()

        # 查询条件选择
        filter_layout = QHBoxLayout()

        self.year_combo = QComboBox()
        self.year_combo.addItem("全部年份", None)
        current_year = datetime.now().year
        for year in range(current_year, current_year + 1):
            self.year_combo.addItem(str(year), year)

        self.month_combo = QComboBox()
        self.month_combo.addItem("全部月份", None)
        for month in range(1, 13):
            self.month_combo.addItem(f"{month}月", month)

        self.day_combo = QComboBox()
        self.day_combo.addItem("全部日期", None)
        for day in range(1, 32):
            self.day_combo.addItem(str(day), day)

        filter_layout.addWidget(QLabel("年份:"))
        filter_layout.addWidget(self.year_combo)
        filter_layout.addWidget(QLabel("月份:"))
        filter_layout.addWidget(self.month_combo)
        filter_layout.addWidget(QLabel("日期:"))
        filter_layout.addWidget(self.day_combo)

        query_btn = QPushButton("查询")
        query_btn.setFixedWidth(100)
        query_btn.setStyleSheet("""
            background-color: #3498db;
            color: white;
            padding: 5px;
            border-radius: 4px;
        """)
        query_btn.clicked.connect(self.query_history)
        filter_layout.addWidget(query_btn)

        history_layout.addLayout(filter_layout)

        # 历史记录表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(3)
        self.history_table.setHorizontalHeaderLabels(["日期", "加工数量", "记录ID"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 平分列宽
        # self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        # self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        # self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        history_layout.addWidget(self.history_table)

        # 清空记录按钮
        clear_layout = QHBoxLayout()
        clear_layout.addStretch()

        self.clear_btn = QPushButton("清空历史记录")
        self.clear_btn.setStyleSheet("""
            background-color: #e74c3c;
            color: white;
            padding: 8px 15px;
            border-radius: 5px;
            font-weight: bold;
        """)
        self.clear_btn.setFixedWidth(150)
        self.clear_btn.clicked.connect(self.show_clear_dialog)
        clear_layout.addWidget(self.clear_btn)

        history_layout.addLayout(clear_layout)
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        self.setLayout(layout)
        self.query_history()  # 初始查询所有历史记录

    def increment_count(self):
        today = datetime.now().strftime("%Y-%m-%d")

        # 检查是否已有今日记录
        self.cursor.execute("SELECT id, count FROM production_history WHERE date = ?", (today,))
        result = self.cursor.fetchone()

        if result:
            # 更新记录
            record_id, current_count = result
            new_count = current_count + 1
            self.cursor.execute("UPDATE production_history SET count = ? WHERE id = ?",
                                (new_count, record_id))
        else:
            # 创建新记录
            self.cursor.execute("INSERT INTO production_history (date, count) VALUES (?, 1)",
                                (today,))
            new_count = 1

        self.conn.commit()
        self.update_daily_count()
        return new_count

    def update_daily_count(self):
        today = datetime.now().strftime("%Y-%m-%d")
        self.cursor.execute("SELECT count FROM production_history WHERE date = ?", (today,))
        result = self.cursor.fetchone()
        count = result[0] if result else 0
        self.daily_count_label.setText(f"今日加工数量: {count}")

    def query_history(self):
        year = self.year_combo.currentData()
        month = self.month_combo.currentData()
        day = self.day_combo.currentData()

        query = "SELECT date, count, id FROM production_history"
        conditions = []
        params = []

        if year:
            conditions.append("strftime('%Y', date) = ?")
            params.append(str(year))
        if month:
            conditions.append("strftime('%m', date) = ?")
            params.append(f"{month:02d}")
        if day:
            conditions.append("strftime('%d', date) = ?")
            params.append(f"{day:02d}")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY date DESC"

        self.cursor.execute(query, params)
        results = self.cursor.fetchall()

        self.history_table.setRowCount(len(results))
        for row_idx, (date_str, count, record_id) in enumerate(results):
            self.history_table.setItem(row_idx, 0, QTableWidgetItem(date_str))
            self.history_table.setItem(row_idx, 1, QTableWidgetItem(str(count)))
            self.history_table.setItem(row_idx, 2, QTableWidgetItem(str(record_id)))

        # 添加以下代码以居中显示表格数据
        for row in range(self.history_table.rowCount()):
            for col in range(self.history_table.columnCount()):
                item = self.history_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)

    def show_clear_dialog(self):
        # 先检查是否有数据可清空
        self.cursor.execute("SELECT COUNT(*) FROM production_history")
        count = self.cursor.fetchone()[0]

        if count == 0:
            QMessageBox.information(self, "提示", "没有可清空的历史记录！")
            return

        dialog = ClearHistoryDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.clear_history()

    def clear_history(self):
        self.cursor.execute("DELETE FROM production_history")
        self.conn.commit()
        self.query_history()
        self.update_daily_count()
        QMessageBox.information(self, "成功", "历史记录已清空！")

    def check_date_change(self):
        # 检查日期是否变更（跨天）
        now = datetime.now()
        if not hasattr(self, 'last_check_date'):
            self.last_check_date = now.date()

        if now.date() != self.last_check_date:
            self.last_check_date = now.date()
            self.update_daily_count()

    def process_signal(self, signal_value):
        """
        处理PLC信号，检测V750.0的上升沿进行计数
        :param signal_value: 当前信号值 (True/False)
        """
        # 检测上升沿（从False变为True）
        if not self.last_signal and signal_value:
            self.increment_count()  # 信号触发时增加计数

        # 更新最后信号状态
        self.last_signal = signal_value


class ClearHistoryDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("清空历史记录")
        self.setFixedSize(400, 250)

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # 警告文本
        warning_label = QLabel("您确定要清空所有历史记录吗？")
        warning_label.setStyleSheet("""
            font-weight: bold;
            font-size: 16px;
            color: #c0392b;
        """)
        warning_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning_label)

        # 提示文本
        info_label = QLabel("此操作不可逆，请输入密码确认:")
        info_label.setStyleSheet("font-size: 14px;")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)

        # 密码输入
        password_layout = QHBoxLayout()
        password_layout.addStretch()

        password_container = QWidget()
        password_container.setFixedWidth(300)
        password_inner = QVBoxLayout(password_container)

        password_inner.addWidget(QLabel("密码:"))

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("输入密码")
        self.password_input.setFixedHeight(40)
        password_inner.addWidget(self.password_input)

        password_layout.addWidget(password_container)
        password_layout.addStretch()
        layout.addLayout(password_layout)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setFixedSize(120, 40)
        self.cancel_btn.setStyleSheet("""
            background-color: #95a5a6;
            color: white;
            border-radius: 4px;
            font-size: 14px;
        """)
        self.cancel_btn.clicked.connect(self.reject)

        self.confirm_btn = QPushButton("确认清空")
        self.confirm_btn.setFixedSize(120, 40)
        self.confirm_btn.setStyleSheet("""
            background-color: #e74c3c;
            color: white;
            font-weight: bold;
            border-radius: 4px;
            font-size: 14px;
        """)
        self.confirm_btn.clicked.connect(self.verify_password)

        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.confirm_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def verify_password(self):
        if self.password_input.text() == "123456":
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "密码错误！")
            self.password_input.clear()