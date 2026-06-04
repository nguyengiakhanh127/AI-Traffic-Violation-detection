from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QLineEdit, QComboBox, QPushButton, QDateTimeEdit)
from PyQt6.QtCore import Qt, QDateTime
from gui.shared_components.event_broker import app_broker

from core.rules import ViolationRegistry, VehicleRegistry
from utils.enums import TrafficVehicleType

class FilterPanel(QWidget):
    # ... [__init__ và _setup_ui GIỮ NGUYÊN] ...
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FilterPanel")
        self.setStyleSheet(
        """
            #FilterPanel { background-color: #1a1a1c; border-radius: 8px; }
            QLabel { color: #aaaaaa; font-size: 12px; }
            QLineEdit, QComboBox, QDateTimeEdit { 
                background-color: #2b2b2d; color: white; border: 1px solid #444; 
                border-radius: 4px; padding: 5px; min-height: 20px;
            }
            QPushButton#BtnSearch { background-color: #f39c12; color: #111; font-weight: bold; border-radius: 4px; padding: 6px 15px; }
            QPushButton#BtnSearch:hover { background-color: #e67e22; }
            QPushButton#BtnReset { background-color: transparent; color: #f39c12; font-weight: bold; }
            QPushButton#BtnReset:hover { text-decoration: underline; }
        """)
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("Tìm kiếm")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(15)

        grid.addWidget(QLabel("Thời gian từ:"), 0, 0)
        self.dt_start = QDateTimeEdit(QDateTime.currentDateTime().addDays(-1))
        self.dt_start.setDisplayFormat("dd/MM/yyyy HH:mm")
        grid.addWidget(self.dt_start, 1, 0)

        grid.addWidget(QLabel("Thời gian đến:"), 0, 1)
        self.dt_end = QDateTimeEdit(QDateTime.currentDateTime())
        self.dt_end.setDisplayFormat("dd/MM/yyyy HH:mm")
        grid.addWidget(self.dt_end, 1, 1)

        grid.addWidget(QLabel("Biển số:"), 2, 0)
        self.input_plate = QLineEdit()
        self.input_plate.setPlaceholderText("Nhập biển số...")
        grid.addWidget(self.input_plate, 3, 0, 1, 2)

        grid.addWidget(QLabel("Loại cảnh báo:"), 0, 2)
        self.combo_error = QComboBox()
        self.combo_error.addItem("--- Tất cả ---", userData=None)
        
        for name_vn, code_en in ViolationRegistry.get_all_for_ui():
            self.combo_error.addItem(name_vn, userData=code_en)
                
        grid.addWidget(self.combo_error, 1, 2)

        grid.addWidget(QLabel("Đối tượng:"), 2, 2)
        self.combo_vehicle = QComboBox()
        self.combo_vehicle.addItem("--- Tất cả ---", userData=None)
        
        for e in TrafficVehicleType:
            if e not in [TrafficVehicleType.UNKNOWN, TrafficVehicleType.SPECIAL]:
                name_vn = VehicleRegistry.get_name(e)
                self.combo_vehicle.addItem(name_vn, userData=e.name)
                
        grid.addWidget(self.combo_vehicle, 3, 2)
        layout.addLayout(grid)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_reset = QPushButton("Làm mới bộ lọc")
        btn_reset.setObjectName("BtnReset")
        btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset.clicked.connect(self.reset_filters)

        btn_search = QPushButton("Tìm kiếm")
        btn_search.setObjectName("BtnSearch")
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_search.clicked.connect(self.emit_search)

        btn_layout.addWidget(btn_reset)
        btn_layout.addWidget(btn_search)
        layout.addLayout(btn_layout)

        grid.addWidget(QLabel("Trạng thái:"), 0, 3)
        self.combo_status = QComboBox()
        self.combo_status.addItem("Chờ kiểm duyệt", userData=0) 
        self.combo_status.addItem("Đã duyệt", userData=1)
        self.combo_status.addItem("Đã hủy bỏ", userData=-1)
        grid.addWidget(self.combo_status, 1, 3)

    def reset_filters(self):
        self.dt_start.setDateTime(QDateTime.currentDateTime().addDays(-1))
        self.dt_end.setDateTime(QDateTime.currentDateTime())
        self.input_plate.clear()
        self.combo_error.setCurrentIndex(0)
        self.combo_vehicle.setCurrentIndex(0)
        self.emit_search() 

    def emit_search(self):
        """[CẬP NHẬT KEY]: Đồng bộ tên Key với DatabaseService mới"""
        filters = {
            "start_time": self.dt_start.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "end_time": self.dt_end.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "bien_so": self.input_plate.text().strip(),             # Đổi từ 'plate'
            "ma_loi": self.combo_error.currentData(),               # Đổi từ 'error_code'
            "loai_xe": self.combo_vehicle.currentData(),            # Đổi từ 'vehicle_type'
            "trang_thai": self.combo_status.currentData()           # Đổi từ 'status'
        }
        app_broker.request_search_violations.emit(filters)