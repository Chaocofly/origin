# license_generator.py
import sys
import os
import json
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QDateEdit,
    QGroupBox, QFormLayout, QFileDialog, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from TOOL.License import LicenseManager



class LicenseGenerator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("许可证生成工具")
        self.setGeometry(300, 300, 650, 550)

        self.license_manager = LicenseManager()
        self.license_data = None

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 机器ID部分
        machine_group = QGroupBox("机器信息")
        machine_layout = QFormLayout()

        self.machine_id_input = QLineEdit()
        self.machine_id_input.setPlaceholderText("输入机器ID或从剪贴板粘贴")
        self.machine_id_input.setMinimumWidth(400)
        machine_layout.addRow("目标机器ID:", self.machine_id_input)

        self.generate_id_btn = QPushButton("生成当前机器ID")
        self.generate_id_btn.clicked.connect(self.generate_current_id)
        machine_layout.addRow(self.generate_id_btn)

        self.current_id_label = QLabel("")
        self.current_id_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.current_id_label.setStyleSheet("font-family: 'Courier New'; font-size: 10pt;")
        machine_layout.addRow("当前机器ID:", self.current_id_label)

        machine_group.setLayout(machine_layout)
        main_layout.addWidget(machine_group)

        # 许可证信息部分
        license_group = QGroupBox("许可证设置")
        license_layout = QFormLayout()

        self.customer_input = QLineEdit("授权客户")
        license_layout.addRow("客户名称:", self.customer_input)

        # 添加永久许可证选项
        self.permanent_check = QCheckBox("永久许可证")
        self.permanent_check.setChecked(True)
        self.permanent_check.stateChanged.connect(self.toggle_expiry_date)
        license_layout.addRow("授权类型:", self.permanent_check)

        self.expiry_date_edit = QDateEdit()
        self.expiry_date_edit.setCalendarPopup(True)
        self.expiry_date_edit.setDate(QDate.currentDate().addMonths(3))
        self.expiry_date_edit.setEnabled(False)  # 默认禁用
        license_layout.addRow("到期日期:", self.expiry_date_edit)

        license_group.setLayout(license_layout)
        main_layout.addWidget(license_group)

        # 操作按钮
        button_layout = QHBoxLayout()

        self.generate_btn = QPushButton("生成许可证")
        self.generate_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        self.generate_btn.clicked.connect(self.generate_license)
        button_layout.addWidget(self.generate_btn)

        self.save_btn = QPushButton("保存许可证文件")
        self.save_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 8px;")
        self.save_btn.clicked.connect(self.save_license)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)

        main_layout.addLayout(button_layout)

        # 许可证预览
        preview_group = QGroupBox("许可证预览")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("font-family: 'Courier New'; font-size: 10pt;")
        preview_layout.addWidget(self.preview_text)

        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)

        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("就绪")

        # 初始化当前机器ID
        self.generate_current_id()

        # 设置默认样式
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid gray;
                border-radius: 5px;
                margin-top: 0.5em;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QLabel {
                font-size: 10pt;
            }
        """)

    def toggle_expiry_date(self, state):
        """切换到期日期控件的启用状态"""
        if state == Qt.Checked:
            self.expiry_date_edit.setEnabled(False)
        else:
            self.expiry_date_edit.setEnabled(True)

    def generate_current_id(self):
        """生成并显示当前机器的ID"""
        machine_id = self.license_manager.get_machine_id()
        self.current_id_label.setText(machine_id)
        self.status_bar.showMessage(f"当前机器ID已生成 - 长度: {len(machine_id)}字符")

    def generate_license(self):
        """生成许可证数据"""
        machine_id = self.machine_id_input.text().strip()
        if not machine_id:
            QMessageBox.warning(self, "缺少信息", "请输入目标机器ID")
            return

        customer = self.customer_input.text().strip() or "授权客户"

        expiry_date = None
        if not self.permanent_check.isChecked():
            if self.expiry_date_edit.date() > QDate.currentDate():
                expiry_date = self.expiry_date_edit.date().toPython()
            else:
                QMessageBox.warning(self, "无效日期", "到期日期必须在今天之后")
                return

        try:
            # 生成许可证数据
            self.license_data = self.license_manager.generate_license_data(
                machine_id,
                expiry_date
            )

            # 更新预览
            self.preview_text.setPlainText(json.dumps(self.license_data, indent=2))
            self.save_btn.setEnabled(True)

            # 显示成功消息
            license_type = "永久许可证" if not expiry_date else f"限时许可证 (有效期至 {expiry_date})"
            self.status_bar.showMessage(
                f"已为机器ID: {machine_id[:8]}... 生成{license_type}"
            )

        except Exception as e:
            QMessageBox.critical(self, "生成错误", f"生成许可证时出错: {str(e)}")
            self.status_bar.showMessage("生成失败")

    def save_license(self):
        """保存许可证文件"""
        if not self.license_data:
            QMessageBox.warning(self, "无数据", "请先生成许可证数据")
            return

        # 选择保存位置
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存许可证文件",
            "license.lic",
            "许可证文件 (*.lic)"
        )

        if file_path:
            try:
                # 保存文件
                self.license_manager.save_license(self.license_data, file_path)

                # 显示成功消息
                QMessageBox.information(
                    self,
                    "保存成功",
                    f"许可证文件已保存至:\n{file_path}"
                )
                self.status_bar.showMessage(f"许可证已保存: {os.path.basename(file_path)}")

            except Exception as e:
                QMessageBox.critical(self, "保存错误", f"保存许可证文件时出错: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置字体
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = LicenseGenerator()
    window.show()
    sys.exit(app.exec())