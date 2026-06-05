from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QPushButton, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from gui.shared_components.event_broker import app_broker
from PyQt6.QtGui import QFont, QBrush, QColor

from core.rules import ViolationRegistry, VehicleRegistry
from utils.enums import TrafficVehicleType, ViolationType
from utils import paths
from datetime import datetime 
import os

class DataTableWidget(QWidget):
    # ... [__init__ và _setup_ui GIỮ NGUYÊN] ...
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DataTableWrap")
        self.setStyleSheet(
        """
            QTableWidget { background-color: #1a1a1c; color: white; border: none; gridline-color: #2b2b2d; }
            QTableWidget::item { padding: 5px; border-bottom: 1px solid #2b2b2d; }
            QTableWidget::item:selected { background-color: #3d342b; color: #f39c12; }
            QHeaderView::section { background-color: #2b2b2d; color: #aaaaaa; font-weight: bold; border: none; padding: 8px; text-align: left; }
            QPushButton.PageBtn { background-color: transparent; color: white; font-size: 16px; font-weight: bold; }
            QPushButton.PageBtn:hover { color: #f39c12; }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title_layout = QHBoxLayout()
        lbl_title = QLabel("📄 Dữ liệu")
        lbl_title.setStyleSheet("color: #f39c12; font-weight: bold; font-size: 14px;")
        title_layout.addWidget(lbl_title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        self.table = QTableWidget()
        headers = ["STT", "Thời gian", "Nguồn (Camera)", "Loại cảnh báo", "Đối tượng", "Làn", "Biển số"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.table)

        page_layout = QHBoxLayout()
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "back.png")))
        self.btn_prev.setProperty("class", "PageBtn")
        self.btn_next = QPushButton()
        self.btn_next.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "next.png")))
        self.btn_next.setProperty("class", "PageBtn")
        self.lbl_page = QLabel("Trang 1 / 1")
        self.lbl_page.setStyleSheet("color: #aaaaaa;")

        page_layout.addStretch()
        page_layout.addWidget(self.btn_prev)
        page_layout.addWidget(self.lbl_page)
        page_layout.addWidget(self.btn_next)
        page_layout.addStretch()
        layout.addLayout(page_layout)


    def load_data(self, data_list: list, current_page: int, total_pages: int):
        self.table.blockSignals(True)
        self.table.setRowCount(len(data_list))

        for row_idx, record in enumerate(data_list):
            stt_item = QTableWidgetItem(str(row_idx + 1))
            stt_item.setData(Qt.ItemDataRole.UserRole, record) 
            
            raw_error_code = record.get('ma_loi_vi_pham', '') 
            ui_error_name = raw_error_code 
            
            for v_type in ViolationType:
                if ViolationRegistry.get_code(v_type) == raw_error_code:
                    ui_error_name = ViolationRegistry.get_name(v_type)
                    break

            raw_time = record.get('thoi_gian_vi_pham', '') 
            time_str = raw_time.strftime("%d/%m/%Y %H:%M:%S") if isinstance(raw_time, datetime) else str(raw_time)

            ui_vehicle_name = record.get('loai_phuong_tien', 'Không xác định')
            self.table.setItem(row_idx, 4, QTableWidgetItem(ui_vehicle_name))

            # [THÊM MỚI]: Lấy tên camera từ record
            camera_name = record.get('ten_camera', 'Không xác định')

            self.table.setItem(row_idx, 0, stt_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(time_str))
            
            # [THÊM MỚI]: Cột Nguồn Camera
            cam_item = QTableWidgetItem(camera_name)
            cam_item.setForeground(QBrush(QColor("#a8dadc"))) # Màu xanh dương nhạt cho dễ phân biệt
            self.table.setItem(row_idx, 2, cam_item)
            
            self.table.setItem(row_idx, 3, QTableWidgetItem(ui_error_name))
            self.table.setItem(row_idx, 4, QTableWidgetItem(ui_vehicle_name))
            
            raw_lane = record.get('lan_duong', '') 
            ui_lane = raw_lane if (raw_lane and raw_lane != "Ngoài làn") else "-"
            lane_item = QTableWidgetItem(ui_lane)
            lane_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 5, lane_item)

            plate_item = QTableWidgetItem(record.get('bien_so_xe', '')) 
            font = QFont()
            font.setBold(True)
            plate_item.setFont(font)
            plate_item.setForeground(QBrush(QColor("#f39c12"))) 
            self.table.setItem(row_idx, 6, plate_item)

        self.table.blockSignals(False)
        self.lbl_page.setText(f"Trang {current_page} / {max(1, total_pages)}")

    def _on_row_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items: return
        first_col_item = self.table.item(selected_items[0].row(), 0)
        record_data = first_col_item.data(Qt.ItemDataRole.UserRole)
        if record_data:
            app_broker.violation_row_selected.emit(record_data)     