# license_manager.py
import os
import sys
import hashlib
import json
import uuid
import platform
import subprocess
import hmac
from Cryptodome.Cipher import AES
from Cryptodome.Util.Padding import pad, unpad
from PySide6.QtWidgets import QMessageBox


class LicenseManager:
    def __init__(self, license_file="license.dat", key_seed="ZhiKongXiaoJiang"):
        self.license_file = license_file
        self.key_seed = key_seed
        self.hardware_id = self._get_hardware_id()

    def _get_hardware_id(self):
        """获取机器硬件指纹"""
        try:
            # Windows 获取磁盘序列号
            if platform.system() == 'Windows':
                cmd = 'wmic diskdrive get serialnumber'
                result = subprocess.check_output(cmd, shell=True, text=True)
                serials = [line.strip() for line in result.split('\n') if line.strip()]
                return serials[1] if len(serials) > 1 else str(uuid.getnode())

            # Linux 获取机器ID
            elif platform.system() == 'Linux':
                with open('/etc/machine-id', 'r') as f:
                    return f.read().strip()

            # 其他系统使用MAC地址
            else:
                return str(uuid.getnode())

        except Exception:
            return str(uuid.getnode())

    def _generate_key(self):
        """使用HMAC-SHA256基于硬件ID生成密钥"""
        h = hmac.new(self.key_seed.encode(), digestmod=hashlib.sha256)
        h.update(self.hardware_id.encode())
        return h.digest()[:16]  # 使用前16字节作为AES-128密钥

    def _encrypt_license(self, data):
        """加密授权数据"""
        key = self._generate_key()
        cipher = AES.new(key, AES.MODE_CBC)
        ct_bytes = cipher.encrypt(pad(json.dumps(data).encode(), AES.block_size))
        return cipher.iv + ct_bytes

    def _decrypt_license(self, encrypted_data):
        """解密授权数据"""
        try:
            iv = encrypted_data[:16]
            ct = encrypted_data[16:]
            key = self._generate_key()
            cipher = AES.new(key, AES.MODE_CBC, iv=iv)
            pt = unpad(cipher.decrypt(ct), AES.block_size)
            return json.loads(pt.decode())
        except (ValueError, KeyError, json.JSONDecodeError):
            return None

    def generate_license(self, output_file=None):
        """生成当前机器的授权文件"""
        if not output_file:
            output_file = self.license_file

        license_data = {
            "hardware_id": self.hardware_id,
            "product": "智控小匠智能交互管控系统",
            "version": "1.0"
        }

        encrypted = self._encrypt_license(license_data)
        with open(output_file, 'wb') as f:
            f.write(encrypted)

        return True

    def validate_license(self):
        """验证授权文件是否有效"""
        if not os.path.exists(self.license_file):
            return False

        try:
            with open(self.license_file, 'rb') as f:
                encrypted = f.read()

            license_data = self._decrypt_license(encrypted)
            if not license_data:
                return False

            return license_data.get("hardware_id") == self.hardware_id
        except Exception:
            return False

    def show_license_error(self):
        """显示授权错误对话框"""
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("授权验证失败")
        msg.setText("无法验证软件授权！")
        msg.setInformativeText(
            "此软件未授权在当前设备运行。\n\n"
            "请提供以下机器码给供应商获取授权文件：\n"
            f"{self.hardware_id}\n\n"
            "将生成的license.dat文件放置在程序目录下。"
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
        return False


if __name__ == "__main__":
    # 授权文件生成工具（单独运行此文件可生成license.dat）
    manager = LicenseManager()
    if manager.generate_license():
        print(f"授权文件已生成: {manager.license_file}")
        print(f"机器码: {manager.hardware_id}")