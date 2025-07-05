import os
import sys
import snap7
import time
import struct
from PySide6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
                               QPushButton, QStatusBar, QVBoxLayout, QWidget, QHeaderView,
                               QTabWidget, QLabel, QGridLayout, QGroupBox, QHBoxLayout, QLineEdit, QInputDialog,
                               QMessageBox)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QColor, QBrush, QFont, QIcon
from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import QSettings
from TOOL.Tool import ToolManager, ToolManagementTab
from TOOL.Tray import TrayManagementTab  # 添加这行
from TOOL.Product import ProductStatisticsTab
from TOOL.Contorl import  ControlPanelTab
from TOOL.Tool2 import ToolManager2, ToolManagementTab2
from TOOL.Woring import AlarmLogger, AlarmHistoryDialog
import TOOL.icon

class PLCWorker(QThread):
    data_updated = Signal(dict)
    status_message = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, plc_ip, all_addresses, vd_addresses, vb_addresses, refresh_interval=0.5, parent=None):
        super().__init__(parent)
        self.plc_ip = plc_ip
        self.all_addresses = all_addresses
        self.vd_addresses = vd_addresses
        self.vb_addresses = vb_addresses
        self.refresh_interval = refresh_interval
        self.running = False
        self.plc = snap7.client.Client()

    def run(self):
        self.running = True
        try:
            self.status_message.emit(f"正在连接到PLC @ {self.plc_ip}...")
            self.plc.connect(self.plc_ip, 0, 1)

            if self.plc.get_connected():
                self.status_message.emit(f"成功连接到PLC @ {self.plc_ip}")
                self.status_message.emit(
                    f"监控地址: {len(self.all_addresses) + len(self.vd_addresses) + len(self.vb_addresses)}个")

                while self.running:
                    try:
                        # 读取所有类型的数据
                        v_data = self.read_v_bool_registers(self.all_addresses)
                        vd_data = self.read_vd_registers(self.vd_addresses)
                        vb_data = self.read_vb_registers(self.vb_addresses)

                        # 合并所有数据
                        all_data = {**v_data, **vd_data, **vb_data}
                        self.data_updated.emit(all_data)
                        time.sleep(self.refresh_interval)  # 用可调的刷新间隔
                    except Exception as e:
                        self.error_occurred.emit(f"读取错误: {str(e)}")
                        time.sleep(2)
            else:
                self.error_occurred.emit("连接失败: 请检查网络和PLC设置")
        except Exception as e:
            self.error_occurred.emit(f"连接错误: {str(e)}")
        finally:
            if self.plc.get_connected():
                self.plc.disconnect()
            self.status_message.emit("已断开与PLC的连接")

    def stop(self):
        self.running = False
        self.status_message.emit("正在停止监控...")

    def read_v_bool_registers(self, addresses):
        """读取布尔量寄存器"""
        results = {}
        try:
            for addr in addresses:
                byte_addr = addr
                data = self.plc.db_read(1, byte_addr, 1)
                byte_value = data[0]

                for bit_position in range(8):
                    bit_value = (byte_value >> bit_position) & 1
                    results[f"V{addr}.{bit_position}"] = bool(bit_value)

                results[f"VB{addr}"] = byte_value
            return results
        except Exception as e:
            raise Exception(f"读取V寄存器时出错: {e}")

    def read_vd_registers(self, addresses):
        """读取VD寄存器（浮点数）"""
        results = {}
        try:
            for addr in addresses:
                # 读取4个字节（浮点数）
                data = self.plc.db_read(1, addr, 4)

                # S7-200 SMART使用大端字节序(CDAB格式)，转换为小端序(ABCD)
                # 原始字节顺序: [C, D, A, B] -> 转换为 [A, B, C, D]
                # 实际上S7-200 SMART存储格式是: [B3, B2, B1, B0] 其中B3是最高字节
                # 我们需要转换为大端序: [B2, B3, B0, B1]
                converted_bytes = bytes([data[2], data[3], data[0], data[1]])

                # 将字节转换为浮点数（小端序）
                float_value = struct.unpack('>f', converted_bytes)[0]
                results[f"VD{addr}"] = float_value
            return results
        except Exception as e:
            raise Exception(f"读取VD寄存器时出错: {e}")

    def read_vb_registers(self, addresses):
        """读取VB寄存器（字节值）"""
        results = {}
        try:
            for addr in addresses:
                # 读取1个字节
                data = self.plc.db_read(1, addr, 1)
                byte_value = data[0]
                results[f"VB{addr}"] = byte_value
            return results
        except Exception as e:
            raise Exception(f"读取VB寄存器时出错: {e}")


class PLCStatusTable(QTableWidget):
    def __init__(self, addresses, title, descriptions, parent=None):
        super().__init__(parent)
        self.descriptions = descriptions

        self.addresses = addresses
        self.title = title

        # 计算总行数 (每个字节地址有8个位)
        self.row_count = len(addresses) * 8
        self.setRowCount(self.row_count)
        self.setColumnCount(4)  # 地址, 状态, 字节值

        self.setHorizontalHeaderLabels(["地址", "状态", "字节值", "描述"])

        # 设置表格属性
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        # 初始化表格数据
        self.init_table()

    def init_table(self):
        row_index = 0
        for addr in self.addresses:
            byte_value = 0
            for bit in range(8):
                # 地址列
                address_item = QTableWidgetItem(f"V{addr}.{bit}")
                address_item.setTextAlignment(Qt.AlignCenter)
                self.setItem(row_index, 0, address_item)

                # 状态列 (初始为OFF)
                status_item = QTableWidgetItem("OFF")
                status_item.setTextAlignment(Qt.AlignCenter)
                status_item.setBackground(QBrush(QColor(230, 230, 230)))  # 灰色背景
                self.setItem(row_index, 1, status_item)

                # 字节值列 (每8行显示一次)
                if bit == 0:
                    byte_item = QTableWidgetItem(f"VB{addr}: {byte_value}")
                    byte_item.setTextAlignment(Qt.AlignCenter)
                    self.setItem(row_index, 2, byte_item)
                    # 描述列
                    description_text = self.descriptions.get(f"V{addr}.{bit}", "")
                    description_item = QTableWidgetItem(description_text)
                    description_item.setTextAlignment(Qt.AlignCenter)
                    self.setItem(row_index, 3, description_item)

                    self.setSpan(row_index, 2, 8, 1)  # 合并单元格
                elif bit > 0:
                    # 不管是 .0 还是 .1 ... .7 都写描述
                    desc_text = self.descriptions.get(f"V{addr}.{bit}", "")
                    desc_item = QTableWidgetItem(desc_text)
                    desc_item.setTextAlignment(Qt.AlignCenter)
                    self.setItem(row_index, 3, desc_item)

                row_index += 1

    def update_data(self, data):
        row_index = 0
        for addr in self.addresses:
            byte_value = data.get(f"VB{addr}", 0)
            for bit in range(8):
                address = f"V{addr}.{bit}"
                status = data.get(address, False)

                # 更新状态列
                status_item = self.item(row_index, 1)
                if status:
                    status_item.setText("ON")
                    status_item.setBackground(QBrush(QColor(144, 238, 144)))  # 浅绿色
                else:
                    status_item.setText("OFF")
                    status_item.setBackground(QBrush(QColor(230, 230, 230)))  # 灰色

                # 更新字节值列 (只在第一行更新)
                if bit == 0:
                    byte_item = self.item(row_index, 2)
                    byte_item.setText(f"VB{addr}: {byte_value}")

                row_index += 1


class RobotStatusTable(QTableWidget):
    """机器人状态监控表"""

    def __init__(self, status_definitions, parent=None):
        super().__init__(parent)
        self.status_definitions = status_definitions

        # 设置表格
        self.setRowCount(len(status_definitions))
        self.setColumnCount(5)  # 序号, 状态名称, 地址, 当前值, 状态描述
        self.setHorizontalHeaderLabels(["序号", "状态名称", "地址", "当前值", "状态描述"])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 平分列宽

        # # 设置表格属性
        # self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 序号列自动调整
        # self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # 名称列拉伸
        # self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 地址列自动调整
        # self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 值列自动调整
        # self.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)  # 描述列拉伸

        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        # 初始化表格
        self.init_table()

    def init_table(self):
        for row, status in enumerate(self.status_definitions):
            # 序号
            seq_item = QTableWidgetItem(str(status["id"]))
            seq_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, seq_item)

            # 状态名称
            name_item = QTableWidgetItem(status["name"])
            name_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 1, name_item)

            # 地址
            addr_item = QTableWidgetItem(f"VB{status['address']}")
            addr_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 2, addr_item)

            # 当前值 (初始化为0)
            value_item = QTableWidgetItem("0")
            value_item.setTextAlignment(Qt.AlignCenter)
            value_item.setBackground(QBrush(QColor(230, 230, 230)))
            self.setItem(row, 3, value_item)

            # 状态描述
            desc_item = QTableWidgetItem("未读取")
            desc_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 4, desc_item)

    def update_data(self, data):
        for row, status in enumerate(self.status_definitions):
            value = data.get(f"VB{status['address']}", 0)
            value_item = self.item(row, 3)
            desc_item = self.item(row, 4)

            # 更新值
            value_item.setText(str(value))

            # 根据状态定义解释值
            if "value_map" in status:
                mapped_value = status["value_map"].get(value, "未知状态")
                desc_item.setText(mapped_value)
            else:
                desc_item.setText(f"原始值: {value}")

            # 设置背景色
            if value > 0:
                value_item.setBackground(QBrush(QColor(144, 238, 144)))  # 浅绿色
                desc_item.setBackground(QBrush(QColor(144, 238, 144)))  # 浅绿色
            else:
                value_item.setBackground(QBrush(QColor(230, 230, 230)))  # 灰色
                desc_item.setBackground(QBrush(QColor(230, 230, 230)))  # 灰色


class RobotDataTable(QTableWidget):
    """机器人数据监控表（浮点数）"""

    def __init__(self, data_definitions, parent=None):
        super().__init__(parent)
        self.data_definitions = data_definitions

        # 设置表格
        self.setRowCount(len(data_definitions))
        self.setColumnCount(4)  # 数据名称, 地址, 当前值, 单位
        self.setHorizontalHeaderLabels(["数据名称", "地址", "当前值", "单位"])

        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 平分列宽

        # # 设置表格属性
        # self.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # 名称列拉伸
        # self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 地址列自动调整
        # self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)  # 值列自动调整
        # self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # 单位列自动调整

        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        # 初始化表格
        self.init_table()

    def init_table(self):
        for row, data in enumerate(self.data_definitions):
            # 数据名称
            name_item = QTableWidgetItem(data["name"])
            name_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, name_item)

            # 地址
            addr_item = QTableWidgetItem(f"VD{data['address']}")
            addr_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 1, addr_item)

            # 当前值 (初始化为0.0)
            value_item = QTableWidgetItem("0.0000")
            value_item.setTextAlignment(Qt.AlignCenter)
            value_item.setBackground(QBrush(QColor(230, 230, 230)))
            self.setItem(row, 2, value_item)

            # 单位
            unit_item = QTableWidgetItem(data.get("unit", ""))
            unit_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 3, unit_item)

    def update_data(self, data):
        for row, item in enumerate(self.data_definitions):
            value = data.get(f"VD{item['address']}", 0.0)
            value_item = self.item(row, 2)

            # 更新值，保留4位小数
            value_item.setText(f"{value:.4f}")

            # 设置背景色
            if abs(value) > 0.001:
                value_item.setBackground(QBrush(QColor(173, 216, 230)))  # 浅蓝色
            else:
                value_item.setBackground(QBrush(QColor(230, 230, 230)))  # 灰色


class PLCStatusWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("MyCompany", "PLCMonitorApp")
        self.setWindowTitle("智控小匠只能交互管控系统")
        self.setGeometry(100, 100, 1200, 800)
        self.setWindowIcon(QIcon(":/logo.ico"))
        # 初始化刀具管理器
        self.tool_manager = ToolManager()
        self.group_summary_labels = {}  # 存储每个组的摘要标签
        self.status_indicators = {}  # 存储状态指示灯
        self.alarm_logger = AlarmLogger()
        # 创建第二个刀具管理器（使用 V800.0 信号）
        self.tool_manager2 = ToolManager2(plc_callback=self.set_800_7_signal)
        # 初始化刀具管理器时传递回调函数
        self.tool_manager = ToolManager(plc_callback=self.set_750_7_signal)
        # 位描述字典
        self.bit_descriptions = {
            #ROBOT-DO
            "V100.0": "DO-0", "V100.1": "DO-1", "V100.2": "DO-2", "V100.3": "DO-3", "V100.4": "DO-4", "V100.5": "DO-5", "V100.6": "DO-6",
            "V100.7": "DO-7", "V101.0": "DO-8", "V101.1": "DO-9", "V101.2": "DO-10", "V101.3": "DO-11", "V101.4": "DO-12", "V101.5": "DO-13",
            "V101.6": "DO-14", "V101.7": "DO-15", "V102.0": "DO-16", "V102.1": "DO-17", "V102.2": "DO-18", "V102.3": "DO-19", "V102.4": "DO-20",
            "V102.5": "DO-21", "V102.6": "DO-22", "V102.7": "DO-23", "V103.0": "DO-24", "V103.1": "DO-25", "V103.2": "DO-26", "V103.3": "DO-27",
            "V103.4": "DO-28", "V103.5": "DO-29", "V103.6": "DO-30", "V103.7": "DO-31",
            # ROBOT-DI
            "V200.0": "DI-0", "V200.1": "DI-1", "V200.2": "DI-2", "V200.3": "DI-3", "V200.4": "DI-4", "V200.5": "DI-5", "V200.6": "DI-6", "V200.7": "DI-7",
            "V201.0": "DI-8", "V201.1": "DI-9", "V201.2": "DI-10", "V201.3": "DI-11", "V201.4": "DI-12", "V201.5": "DI-13", "V201.6": "DI-14", "V201.7": "DI-15",
            "V202.0": "DI-16", "V202.1": "DI-17", "V202.2": "DI-18", "V202.3": "DI-19", "V202.4": "DI-20", "V202.5": "DI-21", "V202.6": "DI-22", "V202.7": "DI-23",
            "V203.0": "DI-24", "V203.1": "DI-25", "V203.2": "DI-26", "V203.3": "DI-27", "V203.4": "DI-28", "V203.5": "DI-29", "V203.6": "DI-30", "V203.7": "DI-31",
            # controlBox
            "V300.0": "控制箱DO0", "V300.1": "控制箱DO1", "V300.2": "控制箱DO2", "V300.3": "控制箱DO3", "V300.4": "控制箱DO4", "V300.5": "控制箱DO5", "V300.6": "控制箱DO6",
            "V300.7": "控制箱DO7", "V301.0": "控制箱CO0", "V301.1": "控制箱CO1", "V301.2": "控制箱CO2", "V301.3": "控制箱CO3", "V301.4": "控制箱CO4", "V301.5": "控制箱CO5",
            "V301.6": "控制箱CO6", "V301.7": "控制箱CO7",
            # control
            "V400.0": "暂停", "V400.1": "恢复", "V400.2": "启动", "V400.3": "停止", "V400.4": "移动至工作原点", "V400.5": "手自动切换", "V400.6":"None", "V400.7":"None",
            # 机床1-IN
            "V600.0":"IN-0", "V600.1":"IN-1", "V600.2":"IN-2", "V600.3":"IN-3", "V600.4":"IN-4", "V600.5":"IN-5", "V600.6":"IN-6", "V600.7":"IN-7","V601.0":"IN-8", "V601.1":"IN-9",
            "V601.2":"IN-10", "V601.3":"IN-11", "V601.4":"IN-12", "V601.5":"IN-13", "V601.6":"IN-14", "V601.7":"IN-15",
            # 机床1-OUT
            "V700.0":"OUT-0", "V700.1":"OUT-1", "V700.2":"OUT-2", "V700.3":"OUT-3", "V700.4":"OUT-4", "V700.5":"OUT-5", "V700.6":"OUT-6", "V700.7":"OUT-7", "V701.0":"OUT-8",
            "V701.1":"OUT-9", "V701.2":"OUT-10", "V701.3":"OUT-11", "V701.4":"OUT-12", "V701.5":"OUT-13", "V701.6":"OUT-14", "V701.7":"OUT-15",
            # 机床2-IN
            "V800.0": "IN-0", "V800.1": "IN-1", "V800.2": "IN-2", "V800.3": "IN-3", "V800.4": "IN-4", "V800.5": "IN-5", "V800.6": "IN-6", "V800.7": "IN-7", "V801.0": "IN-8",
            "V801.1": "IN-9", "V801.2": "IN-10", "V801.3": "IN-11", "V801.4": "IN-12", "V801.5": "IN-13", "V801.6": "IN-14", "V801.7": "IN-15",
            # 机床2-OUT
            "V900.0": "OUT-0", "V900.1": "OUT-1", "V900.2": "OUT-2", "V900.3": "OUT-3", "V900.4": "OUT-4", "V900.5": "OUT-5", "V900.6": "OUT-6", "V900.7": "OUT-7", "V901.0": "OUT-8",
            "V901.1": "OUT-9", "V901.2": "OUT-10", "V901.3": "OUT-11", "V901.4": "OUT-12", "V901.5": "OUT-13", "V901.6": "OUT-14", "V901.7": "OUT-15",

        }

        # PLC配置
        self.PLC_IP = '192.168.58.10'  # 替换为实际PLC IP

        # 定义不同组的寄存器地址
        self.register_groups = {
            "机器人 I/O": [100, 101, 102, 103, 200, 201, 202, 203],
            "控制信号": [300, 301,400],
            "机床A I/O": [600, 601, 700, 701, 750],
            "机床B I/O": [800, 801, 900, 901]
        }

        # 所有布尔量地址的并集
        self.all_addresses = []
        for group in self.register_groups.values():
            self.all_addresses.extend(group)

        # 机器人状态定义 (根据第二个表格)
        self.robot_status_definitions = [
            {"id": 1, "name": "使能状态", "address": 1001,
             "value_map": {0: "未使能", 1: "使能"}},
            {"id": 2, "name": "机器人模式", "address": 1003,
             "value_map": {0: "自动模式", 1: "手动模式"}},
            {"id": 3, "name": "机器人运行状态", "address": 1005,
             "value_map": {1: "停止", 2: "运行", 3: "暂停", 4: "拖动"}},
            {"id": 4, "name": "工具号", "address": 1007},
            {"id": 5, "name": "工件号", "address": 1009},
            {"id": 6, "name": "急停状态", "address": 1011,
             "value_map": {0: "未急停", 1: "急停"}},
            {"id": 7, "name": "超软限位故障", "address": 1013},
            {"id": 8, "name": "主故障码", "address": 1015},
            {"id": 9, "name": "子故障码", "address": 1017},
            {"id": 10, "name": "碰撞检测", "address": 1019,
             "value_map": {0: "无碰撞", 1: "碰撞"}},
            {"id": 11, "name": "运动到位信号", "address": 1021},
            {"id": 12, "name": "安全停止信号SIO", "address": 1023},
            {"id": 13, "name": "安全停止信号SII", "address": 1025}
        ]

        # 机器人数据定义 (根据第一个表格)
        self.robot_data_definitions = [
            {"name": "关节1位置", "address": 1200, "unit": "度"},
            {"name": "关节2位置", "address": 1204, "unit": "度"},
            {"name": "关节3位置", "address": 1208, "unit": "度"},
            {"name": "关节4位置", "address": 1212, "unit": "度"},
            {"name": "关节5位置", "address": 1216, "unit": "度"},
            {"name": "关节6位置", "address": 1220, "unit": "度"},
            {"name": "关节1速度", "address": 1224, "unit": "度/秒"},
            {"name": "关节2速度", "address": 1228, "unit": "度/秒"},
            {"name": "关节3速度", "address": 1232, "unit": "度/秒"},
            {"name": "关节4速度", "address": 1236, "unit": "度/秒"},
            {"name": "关节5速度", "address": 1240, "unit": "度/秒"},
            {"name": "关节6速度", "address": 1244, "unit": "度/秒"},
            {"name": "关节1电流", "address": 1248, "unit": "A"},
            {"name": "关节2电流", "address": 1252, "unit": "A"},
            {"name": "关节3电流", "address": 1256, "unit": "A"},
            {"name": "关节4电流", "address": 1260, "unit": "A"},
            {"name": "关节5电流", "address": 1264, "unit": "A"},
            {"name": "关节6电流", "address": 1268, "unit": "A"},
            {"name": "关节1扭矩", "address": 1272, "unit": "Nm"},
            {"name": "关节2扭矩", "address": 1276, "unit": "Nm"},
            {"name": "关节3扭矩", "address": 1280, "unit": "Nm"},
            {"name": "关节4扭矩", "address": 1284, "unit": "Nm"},
            {"name": "关节5扭矩", "address": 1288, "unit": "Nm"},
            {"name": "关节6扭矩", "address": 1292, "unit": "Nm"},
            {"name": "TCP位置X", "address": 1296, "unit": "mm"},
            {"name": "TCP位置Y", "address": 1300, "unit": "mm"},
            {"name": "TCP位置Z", "address": 1304, "unit": "mm"},
            {"name": "TCP位置RX", "address": 1308, "unit": "度"},
            {"name": "TCP位置RY", "address": 1312, "unit": "度"},
            {"name": "TCP位置RZ", "address": 1316, "unit": "度"},
            {"name": "TCP速度X", "address": 1320, "unit": "mm/s"},
            {"name": "TCP速度Y", "address": 1324, "unit": "mm/s"},
            {"name": "TCP速度Z", "address": 1328, "unit": "mm/s"},
            {"name": "TCP速度RX", "address": 1332, "unit": "度/s"},
            {"name": "TCP速度RY", "address": 1336, "unit": "度/s"},
            {"name": "TCP速度RZ", "address": 1340, "unit": "度/s"}
        ]

        # 提取机器人状态VB地址
        self.robot_status_vb = [status["address"] for status in self.robot_status_definitions]

        # 提取机器人数据VD地址
        self.robot_data_vd = [data["address"] for data in self.robot_data_definitions]
        self.v_tables = []
        # 初始化UI
        self.init_ui()

        # 工作线程
        self.worker = None

    def init_ui(self):
        # 创建主控件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)


        # 创建标题标签
        title_label = QLabel("智控小匠智能交互管控系统")
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            color: white; 
            padding: 15px;
            background-color: #2c3e50;
            border-radius: 10px;
            margin-bottom: 10px;
        """)
        main_layout.addWidget(title_label)

        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 - 点击'开始监控'连接PLC")

        # 创建控制按钮
        button_layout = QHBoxLayout()

        self.control_button = QPushButton("开始监控")
        self.control_button.setFixedHeight(45)
        self.control_button.setStyleSheet("""
            QPushButton {
                font-size: 16px; 
                font-weight: bold;
                background-color: #4CAF50; 
                color: white;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.control_button.clicked.connect(self.toggle_monitoring)
        button_layout.addWidget(self.control_button)

        # 添加固定IP标签
        ip_label = QLabel(f"PLC IP: {self.PLC_IP}")
        ip_label.setFont(QFont("Arial", 12))
        ip_label.setStyleSheet("color: #7f8c8d; padding: 5px;")
        button_layout.addWidget(ip_label)

        # 添加固定刷新率标签
        self.refresh_label = QLabel("刷新率: 0.1秒")
        self.refresh_label.setFont(QFont("Arial", 12))
        self.refresh_label.setStyleSheet("color: #7f8c8d; padding: 5px;")
        button_layout.addWidget(self.refresh_label)

        # 添加状态指示灯
        status_indicator_layout = QHBoxLayout()
        status_indicator_layout.addWidget(QLabel("状态:"))

        # 创建PLC连接状态指示灯
        plc_indicator_layout = self.create_indicator("PLC连接", "V750.4")
        status_indicator_layout.addLayout(plc_indicator_layout)

        # 创建机器人连接状态指示灯
        robot_indicator_layout = self.create_indicator("机器人", "V750.1")
        status_indicator_layout.addLayout(robot_indicator_layout)

        # 创建机床1连接状态指示灯
        machine1_indicator_layout = self.create_indicator("机床A", "V750.2")
        status_indicator_layout.addLayout(machine1_indicator_layout)

        # 创建机床2连接状态指示灯
        machine2_indicator_layout = self.create_indicator("机床B", "V750.3")
        status_indicator_layout.addLayout(machine2_indicator_layout)

        # 添加指示灯容器
        indicator_container = QWidget()
        indicator_container.setLayout(status_indicator_layout)
        button_layout.addWidget(indicator_container)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMovable(False)
        # 添加刀具管理标签页
        tool_tab = ToolManagementTab(self.tool_manager)
        self.tab_widget.addTab(tool_tab, "刀具管理1")
        # 添加第二个刀具管理标签页
        tool_tab2 = ToolManagementTab2(self.tool_manager2)
        self.tab_widget.addTab(tool_tab2, "刀具管理2")
        # 添加料盘管理标签页
        tray_tab = TrayManagementTab(main_window=self)  # 传递主窗口引用
        self.tab_widget.addTab(tray_tab, "料盘管理")
        # 添加产品统计标签页
        self.product_stats_tab = ProductStatisticsTab()
        self.tab_widget.addTab(self.product_stats_tab, "产品统计")
        # 添加控制面板标签页（作为第一个标签页）
        self.control_tab = ControlPanelTab(self.PLC_IP)
        self.tab_widget.addTab(self.control_tab, "单机调试")
        # 1. 机器人状态标签页
        robot_status_tab = QWidget()
        status_layout = QVBoxLayout(robot_status_tab)

        # 添加标题
        status_title = QLabel("机器人状态监控")
        status_title.setFont(QFont("Arial", 14, QFont.Bold))
        status_title.setStyleSheet("color: #34495e; padding: 10px;")
        status_title.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(status_title)

        # 创建机器人状态表格
        self.robot_status_table = RobotStatusTable(self.robot_status_definitions)
        status_layout.addWidget(self.robot_status_table)

        # 添加标签页
        self.tab_widget.addTab(robot_status_tab, "机器人状态")

        # 创建右上角的翻页按钮布局
        top_right_layout = QHBoxLayout()
        top_right_layout.setAlignment(Qt.AlignRight | Qt.AlignTop)

        # 上一页按钮
        self.prev_button = QPushButton("上一页")
        self.prev_button.setFixedSize(100, 40)  # 适合触摸屏的尺寸
        self.prev_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.prev_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.prev_button.clicked.connect(self.prev_tab)

        # 下一页按钮
        self.next_button = QPushButton("下一页")
        self.next_button.setFixedSize(100, 40)  # 适合触摸屏的尺寸
        self.next_button.setFont(QFont("Arial", 12, QFont.Bold))
        self.next_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        self.next_button.clicked.connect(self.next_tab)

        top_right_layout.addWidget(self.prev_button)
        top_right_layout.addWidget(self.next_button)

        # 将翻页按钮布局添加到主布局（在标题之后，控制按钮之前）
        main_layout.addLayout(top_right_layout)

        self.history_button = QPushButton("查询历史报警")
        self.history_button.clicked.connect(self.show_alarm_history_dialog)

        button_layout.addWidget(self.history_button)



        # 2. 机器人数据标签页
        robot_data_tab = QWidget()
        data_layout = QVBoxLayout(robot_data_tab)

        # 添加标题
        data_title = QLabel("机器人数据监控")
        data_title.setFont(QFont("Arial", 14, QFont.Bold))
        data_title.setStyleSheet("color: #34495e; padding: 10px;")
        data_title.setAlignment(Qt.AlignCenter)
        data_layout.addWidget(data_title)

        # 创建机器人数据表格
        self.robot_data_table = RobotDataTable(self.robot_data_definitions)
        data_layout.addWidget(self.robot_data_table)

        # 添加标签页
        self.tab_widget.addTab(robot_data_tab, "机器人位置")

        # 3. 添加原有的布尔量监控标签页
        for group_name, addresses in self.register_groups.items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)

            # 添加组标题
            group_label = QLabel(f"{group_name} - V寄存器状态")
            group_label.setFont(QFont("Arial", 12, QFont.Bold))
            group_label.setStyleSheet("color: #34495e; padding: 5px;")
            group_label.setAlignment(Qt.AlignCenter)
            tab_layout.addWidget(group_label)

            # 创建并添加表格
            table = PLCStatusTable(addresses, group_name, self.bit_descriptions)

            tab_layout.addWidget(table)
            self.v_tables.append(table)

            # 在init_ui方法中，创建状态摘要的部分修改为：
            summary_group = QGroupBox("状态摘要")
            summary_layout = QGridLayout()

            # 存储每个组的摘要标签
            group_labels = {}

            # 创建摘要标签
            for i, addr in enumerate(addresses):
                # 字节状态摘要
                byte_label = QLabel(f"VB{addr}: 00000000")
                byte_label.setFont(QFont("Courier New", 13))
                summary_layout.addWidget(QLabel(f"VB{addr}:"), i, 0)
                summary_layout.addWidget(byte_label, i, 1)

                # 位状态摘要
                bits_label = QLabel("OFF OFF OFF OFF OFF OFF OFF OFF")
                bits_label.setFont(QFont("Courier New", 13))
                bits_label.setStyleSheet("color: #7f8c8d;")
                summary_layout.addWidget(bits_label, i, 2)

                # 保存标签引用
                group_labels[addr] = (byte_label, bits_label)

            summary_group.setLayout(summary_layout)
            tab_layout.addWidget(summary_group)

            # 💥这里加上这一句，把所有标签注册到大字典里
            self.group_summary_labels[group_name] = group_labels

            # 将标签页添加到标签控件
            self.tab_widget.addTab(tab, group_name)

        # 添加标签页控件到主布局
        main_layout.addWidget(self.tab_widget)

    def create_indicator(self, label_text, signal_address):
        """创建一个指示灯组件"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # 创建指示灯标签
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignCenter)
        label.setFont(QFont("Arial", 8))
        label.setStyleSheet("color: #7f8c8d;")
        layout.addWidget(label)

        # 创建指示灯
        indicator = QLabel()
        indicator.setFixedSize(20, 20)
        indicator.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid gray;")
        layout.addWidget(indicator)

        # 存储指示灯引用
        self.status_indicators[signal_address] = indicator

        return layout
    def toggle_monitoring(self):
        if self.worker and self.worker.isRunning():
            # 停止监控
            self.worker.stop()
            self.control_button.setText("开始监控")
            self.control_button.setStyleSheet("""
                QPushButton {
                    font-size: 16px; 
                    font-weight: bold;
                    background-color: #4CAF50; 
                    color: white;
                    border-radius: 5px;
                    padding: 10px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
        else:
            # 在开始监控时，先将所有指示灯设置为黄色（连接中）
            for indicator in self.status_indicators.values():
                indicator.setStyleSheet("background-color: yellow; border-radius: 10px; border: 1px solid gray;")

            # 固定刷新率为0.1秒
            refresh_interval = 0.01
            self.refresh_label.setText(f"刷新率: {refresh_interval}秒")

            # 启动线程
            self.worker = PLCWorker(
                plc_ip=self.PLC_IP,
                all_addresses=self.all_addresses,
                vd_addresses=self.robot_data_vd,
                vb_addresses=self.robot_status_vb,
                refresh_interval=refresh_interval
            )
            self.worker.data_updated.connect(self.update_all_tables)
            self.worker.status_message.connect(self.status_bar.showMessage)
            self.worker.error_occurred.connect(self.show_error)
            self.worker.finished.connect(self.worker_finished)

            self.control_button.setText("停止监控")
            self.control_button.setStyleSheet("""
                    QPushButton {
                        font-size: 16px; 
                        font-weight: bold;
                        background-color: #f44336; 
                        color: white;
                        border-radius: 5px;
                        padding: 10px;
                    }
                    QPushButton:hover {
                        background-color: #d32f2f;
                    }
                """)
            self.status_bar.showMessage(f"正在启动监控 - IP: {self.PLC_IP} 刷新率: {refresh_interval}秒")
            self.worker.start()
            self.update_nav_buttons()

    def update_all_tables(self, data):
        # 更新机器人状态表
        self.robot_status_table.update_data(data)

        # 更新机器人数据表
        self.robot_data_table.update_data(data)

        # 更新所有V寄存器状态表
        for table in self.v_tables:
            table.update_data(data)
        # 更新状态摘要
        self.update_summary_labels(data)
        # 更新状态栏
        self.status_bar.showMessage(f"最后更新: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        for signal_address, indicator in self.status_indicators.items():
            if signal_address in data:
                if data[signal_address]:
                    indicator.setStyleSheet("background-color: green; border-radius: 10px; border: 1px solid gray;")
                else:
                    indicator.setStyleSheet("background-color: white; border-radius: 10px; border: 1px solid gray;")
            else:
                # 尚未读取到信号时显示黄色
                indicator.setStyleSheet("background-color: yellow; border-radius: 10px; border: 1px solid gray;")
        # 处理刀具信号
        if "V750.0" in data:
            tray_tab = self.tab_widget.widget(2)
            product_tab = self.tab_widget.widget(3)
            if tray_tab and product_tab:
                tray_tab.process_signal(data["V750.0"])
                product_tab.process_signal(data["V750.0"])

        # 在 update_all_tables 方法中添加
        if "VB1003" in data:
            # VB1003 值为 1 表示手动模式
            self.control_tab.set_manual_mode(data["VB1003"] == 1)

        # 处理第二个刀具管理信号 (V800.0)
        if "V800.0" in data:
            tool_tab2 = self.tab_widget.widget(1)  # 根据实际索引调整
            if tool_tab2:
                tool_tab2.process_signal(data["V800.0"])

        # 处理第二个刀具管理信号 (V600.0)
        if "V600.0" in data:
            tool_tab = self.tab_widget.widget(0)  # 根据实际索引调整
            if tool_tab:
                tool_tab.process_signal(data["V600.0"])

        # 机器人状态对应的字段
        status_mapping = {
            "VB1011": "急停状态",
            "VB1019": "碰撞检测",
            "VB1013": "超软限位故障",
            "VB1023": "安全停止信号SIO",
            "VB1025": "安全停止信号SII",
            "VB1015": "主故障码",
            "VB1017": "子故障码"
        }

        for vb_addr, alarm_name in status_mapping.items():
            if vb_addr in data:
                self.alarm_logger.log_state_change(alarm_name, data[vb_addr])

    def show_error(self, message):
        self.status_bar.showMessage(f"错误: {message}")

    def worker_finished(self):
        self.control_button.setText("开始监控")
        self.control_button.setStyleSheet("""
            QPushButton {
                font-size: 16px; 
                font-weight: bold;
                background-color: #4CAF50; 
                color: white;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        # 更新所有指示灯为红色（未连接状态）
        for indicator in self.status_indicators.values():
            indicator.setStyleSheet("background-color:white ; border-radius: 10px; border: 1px solid gray;")
    def closeEvent(self, event):
        # 确保在关闭窗口时停止工作线程
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(2000)  # 等待2秒让线程结束
        event.accept()

    def load_ip_history(self):
        ip_history = self.settings.value("ip_history", [])
        if isinstance(ip_history, str):
            ip_history = [ip_history]
        for ip in ip_history:
            self.ip_combo.addItem(ip)
        if ip_history:
            self.ip_combo.setCurrentIndex(0)
        else:
            self.ip_combo.addItem(self.PLC_IP)
            self.ip_combo.setCurrentIndex(0)

    def save_ip_to_history(self, ip):
        ip_history = self.settings.value("ip_history", [])
        if isinstance(ip_history, str):
            ip_history = [ip_history]
        if ip not in ip_history:
            ip_history.insert(0, ip)
        else:
            ip_history.remove(ip)
            ip_history.insert(0, ip)
        ip_history = ip_history[:5]  # 最多记5个
        self.settings.setValue("ip_history", ip_history)

    def load_refresh_value(self):
        saved_refresh = self.settings.value("refresh_value", "0.5")
        index = self.refresh_combo.findText(saved_refresh)
        if index >= 0:
            self.refresh_combo.setCurrentIndex(index)
        else:
            self.refresh_combo.addItem(saved_refresh)
            self.refresh_combo.setCurrentText(saved_refresh)


    def update_summary_labels(self, data):
        """更新所有组的状态摘要标签"""
        for group_name, addresses in self.register_groups.items():
            group_labels = self.group_summary_labels.get(group_name, {})
            for addr in addresses:
                byte_value = data.get(f"VB{addr}", 0)
                byte_label, bits_label = group_labels.get(addr, (None, None))

                if byte_label and bits_label:
                    # 更新字节值标签
                    byte_label.setText(f"VB{addr}: {byte_value:08b}")  # 显示为8位二进制

                    # 更新位状态标签
                    bit_states = []
                    for bit in range(8):
                        bit_value = (byte_value >> bit) & 1
                        state = "ON" if bit_value else "OFF"
                        # 为ON状态添加颜色标记
                        if bit_value:
                            state = f'<span style="color: green; font-weight: bold;">{state}</span>'
                        bit_states.append(state)

                    # 反转列表，因为位0是最低位，但通常显示从左到右是高位到低位
                    bit_states.reverse()
                    bits_label.setText(" ".join(bit_states))

    # 添加翻页方法
    def prev_tab(self):
        current_index = self.tab_widget.currentIndex()
        if current_index > 0:
            self.tab_widget.setCurrentIndex(current_index - 1)
        self.update_nav_buttons()

    def next_tab(self):
        current_index = self.tab_widget.currentIndex()
        if current_index < self.tab_widget.count() - 1:
            self.tab_widget.setCurrentIndex(current_index + 1)
        self.update_nav_buttons()

    def update_nav_buttons(self):
        """根据当前标签页位置更新按钮状态"""
        current_index = self.tab_widget.currentIndex()
        self.prev_button.setDisabled(current_index == 0)
        self.next_button.setDisabled(current_index == self.tab_widget.count() - 1)

    def set_600_7_signal(self, value):
        """设置 PLC V600.7 信号"""
        plc = snap7.client.Client()
        try:
            plc.connect(self.PLC_IP, 0, 1)
            if plc.get_connected():
                # 读取 VB600
                data = plc.db_read(1, 600, 1)
                byte_value = data[0]

                # 设置或清除第7位 (V600.7)
                if value:
                    new_byte = byte_value | 0x80  # 设置第7位为1
                else:
                    new_byte = byte_value & 0x7F  # 设置第7位为0

                # 写回 VB600
                plc.db_write(1, 600, bytearray([new_byte]))
        except Exception as e:
            print(f"设置 V600.7 信号错误: {str(e)}")
        finally:
            if plc.get_connected():
                plc.disconnect()


    def set_800_7_signal(self, value):
        """设置 PLC V800.7 信号"""
        plc = snap7.client.Client()
        try:
            plc.connect(self.PLC_IP, 0, 1)
            if plc.get_connected():
                # 读取 VB600
                data = plc.db_read(1, 800, 1)
                byte_value = data[0]

                # 设置或清除第7位 (V800.7)
                if value:
                    new_byte = byte_value | 0x80  # 设置第7位为1
                else:
                    new_byte = byte_value & 0x7F  # 设置第7位为0

                # 写回 VB600
                plc.db_write(1, 800, bytearray([new_byte]))
        except Exception as e:
            print(f"设置 V600.7 信号错误: {str(e)}")
        finally:
            if plc.get_connected():
                plc.disconnect()


    # 新增方法：设置 PLC V750.7 信号
    def set_750_7_signal(self, value):
        # 创建一个临时的PLC连接
        plc = snap7.client.Client()
        try:
            plc.connect(self.PLC_IP, 0, 1)
            if plc.get_connected():
                # 读取VB750
                data = plc.db_read(1, 750, 1)
                byte_value = data[0]

                # 设置或清除第7位（V750.7）
                if value:
                    new_byte = byte_value | 0x80  # 设置第7位为1
                else:
                    new_byte = byte_value & 0x7F  # 设置第7位为0

                # 写回VB750
                plc.db_write(1, 750, bytearray([new_byte]))
                self.status_bar.showMessage(f"设置 V750.7 为 {'True' if value else 'False'}")
            else:
                self.status_bar.showMessage("无法设置信号：未连接到PLC")
        except Exception as e:
            self.status_bar.showMessage(f"设置信号错误: {str(e)}")
        finally:
            if plc.get_connected():
                plc.disconnect()


    def show_alarm_history_dialog(self):
        dlg = AlarmHistoryDialog(self.alarm_logger, self)
        dlg.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle("Fusion")

    # 设置全局字体
    font = QFont("Arial", 15)
    app.setFont(font)

    window = PLCStatusWindow()
    window.show()

    sys.exit(app.exec())