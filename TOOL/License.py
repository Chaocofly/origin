# license_manager.py
import os
import sys
import hashlib
import uuid
import json
import platform
import socket
import getpass
import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QPushButton, QHBoxLayout, QApplication, QFileDialog, QDialog, QVBoxLayout, \
    QLabel, QGroupBox


class LicenseManager:
    def __init__(self, app_name="智控小匠智能交互管控系统"):
        self.app_name = app_name
        self.license_file = "license.lic"
        self.valid_machine_id = None
        self.license_data = {}

    def get_machine_id(self):
        """生成基于系统硬件的唯一机器ID"""
        # 获取系统信息组合
        system_info = {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
            "username": getpass.getuser(),
            "mac": ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                             for elements in range(0, 2 * 6, 2)][::-1])
        }

        # 创建唯一哈希
        unique_string = json.dumps(system_info, sort_keys=True)
        return hashlib.sha256(unique_string.encode()).hexdigest()

    def validate_license(self):
        """验证许可证有效性并返回结果"""
        # 检查许可证文件是否存在
        if not os.path.exists(self.license_file):
            # 显示错误对话框并处理用户操作
            return self.show_license_error("未找到许可证文件")

        try:
            # 加载许可证数据
            with open(self.license_file, 'r') as f:
                self.license_data = json.load(f)

            # 验证签名
            license_hash = self.license_data.pop('signature')
            computed_hash = hashlib.sha256(
                json.dumps(self.license_data, sort_keys=True).encode()
            ).hexdigest()

            if license_hash != computed_hash:
                return self.show_license_error("许可证文件已被篡改")

            # 验证机器ID
            current_machine_id = self.get_machine_id()
            if self.license_data.get('machine_id') != current_machine_id:
                return self.show_license_error("未授权在此计算机上运行")

            # 验证有效期
            if "expiry_date" in self.license_data:
                expiry_date = datetime.datetime.strptime(
                    self.license_data["expiry_date"], "%Y-%m-%d"
                ).date()
                today = datetime.date.today()

                if today > expiry_date:
                    days_overdue = (today - expiry_date).days
                    return self.show_license_error(
                        f"许可证已过期 {days_overdue} 天\n"
                        f"到期日期: {expiry_date}"
                    )

            # 验证成功后重新添加签名（因为之前pop了）
            self.license_data['signature'] = license_hash
            return True  # 验证成功

        except Exception as e:
            return self.show_license_error(f"许可证验证失败: {str(e)}")

    def show_license_error(self, message):
        """显示许可证错误消息"""
        error_msg = (
            f"{self.app_name} - 授权错误\n\n"
            f"{message}\n\n"
            "此软件只能在授权计算机上运行。\n"
            "请联系供应商获取有效许可证。"
        )

        # 创建自定义对话框
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("授权错误")
        msg_box.setText(error_msg)

        # 添加获取机器码按钮
        machine_id_btn = msg_box.addButton("获取机器码", QMessageBox.ActionRole)
        import_btn = msg_box.addButton("导入许可证", QMessageBox.ActionRole)
        msg_box.addButton(QMessageBox.Ok)

        result = msg_box.exec()

        # 处理按钮点击
        if msg_box.clickedButton() == machine_id_btn:
            self.show_machine_id_dialog()
            return False  # 返回False表示未解决授权问题
        elif msg_box.clickedButton() == import_btn:
            return self.import_license_file()  # 返回导入结果
        else:
            # 退出应用程序
            return False  # 返回False表示未解决授权问题

    def show_machine_id_dialog(self):
        """显示机器码对话框"""
        machine_id = self.get_machine_id()

        dialog = QDialog()
        dialog.setWindowTitle("机器码信息")
        dialog.setMinimumSize(500, 300)

        layout = QVBoxLayout(dialog)

        # 标题
        title_label = QLabel("您的机器码信息")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 说明文本
        instruction = QLabel(
            "请将以下机器码发送给供应商以获取授权文件：\n"
            "1. 复制机器码\n"
            "2. 通过邮件或其他方式发送给供应商\n"
            "3. 获取license.lic文件后，点击'导入许可证'按钮"
        )
        instruction.setWordWrap(True)
        layout.addWidget(instruction)

        # 机器码显示
        id_group = QGroupBox("机器码")
        id_layout = QVBoxLayout(id_group)

        machine_id_label = QLabel(machine_id)
        machine_id_label.setStyleSheet("""
            font-family: 'Courier New';
            font-size: 12pt;
            background-color: #f0f0f0;
            padding: 10px;
            border: 1px solid #ccc;
        """)
        machine_id_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        id_layout.addWidget(machine_id_label)

        # 复制按钮
        copy_btn = QPushButton("复制机器码")
        copy_btn.clicked.connect(lambda: self.copy_to_clipboard(machine_id))
        id_layout.addWidget(copy_btn)

        layout.addWidget(id_group)

        # 按钮区域
        btn_layout = QHBoxLayout()

        import_btn = QPushButton("导入许可证")
        import_btn.clicked.connect(self.import_license_file)
        btn_layout.addWidget(import_btn)

        exit_btn = QPushButton("退出")
        exit_btn.clicked.connect(sys.exit)
        btn_layout.addWidget(exit_btn)

        layout.addLayout(btn_layout)

        dialog.exec()

    def copy_to_clipboard(self, text):
        """复制文本到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        QMessageBox.information(None, "复制成功", "机器码已复制到剪贴板")

    def import_license_file(self):
        """导入许可证文件，返回导入是否成功"""
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "选择许可证文件",
            "",
            "许可证文件 (*.lic)"
        )

        if file_path:
            try:
                # 复制到当前目录
                import shutil
                shutil.copy(file_path, self.license_file)

                # 重新验证
                if self.validate_license():
                    QMessageBox.information(
                        None,
                        "导入成功",
                        "许可证文件导入成功，请重新启动应用程序"
                    )
                    return True  # 导入并验证成功
                else:
                    QMessageBox.warning(
                        None,
                        "验证失败",
                        "导入的许可证文件验证失败"
                    )
                    return False  # 导入但验证失败
            except Exception as e:
                QMessageBox.critical(
                    None,
                    "导入错误",
                    f"导入许可证文件失败: {str(e)}"
                )
                return False  # 导入失败

        return False  # 用户取消导入

    def generate_license_data(self, machine_id, expiry_date=None):
        """生成许可证数据"""
        license_data = {
            "app_name": self.app_name,
            "machine_id": machine_id,
            "license_type": "永久" if not expiry_date else "限时",
            "customer": "授权用户",
            "issue_date": datetime.date.today().isoformat()
        }

        if expiry_date:
            license_data["expiry_date"] = expiry_date.isoformat()

        # 添加签名
        signature = hashlib.sha256(
            json.dumps(license_data, sort_keys=True).encode()
        ).hexdigest()
        license_data['signature'] = signature

        return license_data

    def save_license(self, license_data, output_file="license.lic"):
        """保存许可证文件"""
        with open(output_file, 'w') as f:
            json.dump(license_data, f, indent=2)

        return output_file

    def get_license_info(self):
        """获取许可证信息用于显示"""
        if not self.license_data:
            try:
                with open(self.license_file, 'r') as f:
                    self.license_data = json.load(f)
            except:
                return {}

        # 创建显示信息
        info = {
            "应用名称": self.license_data.get("app_name", "未知"),
            "客户": self.license_data.get("customer", "未知"),
            "授权类型": self.license_data.get("license_type", "未知"),
            "签发日期": self.license_data.get("issue_date", "未知"),
            "机器ID": self.license_data.get("machine_id", "未知")[:16] + "..."  # 只显示部分ID
        }

        if "expiry_date" in self.license_data:
            expiry_date = datetime.datetime.strptime(
                self.license_data["expiry_date"], "%Y-%m-%d"
            ).date()
            today = datetime.date.today()
            days_left = (expiry_date - today).days

            info["到期日期"] = self.license_data["expiry_date"]
            info["剩余天数"] = f"{days_left} 天"

            if days_left < 0:
                info["状态"] = "已过期"
            elif days_left < 30:
                info["状态"] = f"即将到期 ({days_left}天)"
            else:
                info["状态"] = "有效"
        else:
            info["状态"] = "永久有效"

        return info