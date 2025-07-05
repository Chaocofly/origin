# generate_license_gui.py
import sys
import hashlib
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                               QLabel, QLineEdit, QPushButton, QTextEdit)

class LicenseGenerator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("授权码生成工具")
        self.setGeometry(300, 300, 400, 300)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("请输入对方提供的机器码（Machine ID）："))
        self.input_edit = QTextEdit()
        layout.addWidget(self.input_edit)

        self.gen_button = QPushButton("生成授权码")
        self.gen_button.clicked.connect(self.generate_license)
        layout.addWidget(self.gen_button)

        layout.addWidget(QLabel("生成的授权码："))
        self.output_edit = QTextEdit()
        self.output_edit.setReadOnly(True)
        layout.addWidget(self.output_edit)

        self.setLayout(layout)

    def generate_license(self):
        machine_id = self.input_edit.toPlainText().strip()
        if not machine_id:
            self.output_edit.setPlainText("❌ 请输入机器码")
            return

        license_code = hashlib.sha256(machine_id.encode()).hexdigest()
        self.output_edit.setPlainText(license_code)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = LicenseGenerator()
    win.show()
    sys.exit(app.exec())
