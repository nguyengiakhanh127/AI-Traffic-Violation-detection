# --- START OF FILE gui/features/violation_reviewer/components/data_table.py ---
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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DataTableWrap")
        
        # CSS bám sát phong cách VTV1: Viền ẩn, màu xen kẽ, highlight vàng nhạt
        self.setStyleSheet(
        """
            QTableWidget {
                background-color: #1a1a1c; color: white; border: none; gridline-color: #2b2b2d;
            }
            QTableWidget::item { padding: 5px; border-bottom: 1px solid #2b2b2d; }
            QTableWidget::item:selected { background-color: #3d342b; color: #f39c12; }
            QHeaderView::section {
                background-color: #2b2b2d; color: #aaaaaa; font-weight: bold; border: none; padding: 8px; text-align: left;
            }
            QPushButton.PageBtn { background-color: transparent; color: white; font-size: 16px; font-weight: bold; }
            QPushButton.PageBtn:hover { color: #f39c12; }
        """)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header Title
        title_layout = QHBoxLayout()
        lbl_title = QLabel("📄 Dữ liệu")
        lbl_title.setStyleSheet("color: #f39c12; font-weight: bold; font-size: 14px;")
        title_layout.addWidget(lbl_title)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Bảng dữ liệu
        self.table = QTableWidget()
        headers = ["STT", "Thời gian phát hiện", "Loại cảnh báo", "Đối tượng", "Làn", "Biển số"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # Cấu hình hành vi bảng
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch) # Cột giãn đều
        self.table.verticalHeader().setVisible(False) # Ẩn số dòng mặc định bên trái
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows) # Chọn cả dòng
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # Cấm user sửa chữ trong bảng
        self.table.setShowGrid(False) # Ẩn lưới dọc
        
        # Bắt sự kiện khi user click vào 1 dòng
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        layout.addWidget(self.table)

        # Phân trang (Pagination)
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
            
            # --- [CẬP NHẬT 2]: DỊCH MÃ LỖI (Ví dụ: "DI_SAI_LAN" -> "Đi sai làn") ---
            raw_error_code = record.get('violation_code', '')
            ui_error_name = raw_error_code # Mặc định nếu không dịch được
            
            # Tìm trong bộ Enum xem có mã nào khớp với string từ DB không
            for v_type in ViolationType:
                if ViolationRegistry.get_code(v_type) == raw_error_code:
                    ui_error_name = ViolationRegistry.get_name(v_type)
                    break
            raw_time = record.get('timestamp', '')
            if isinstance(raw_time, datetime):
                # Format lại thành định dạng Tiếng Việt (Ngày/Tháng/Năm Giờ:Phút:Giây)
                time_str = raw_time.strftime("%d/%m/%Y %H:%M:%S")
            else:
                time_str = str(raw_time) # Đề phòng lỗi dữ liệu rỗng

            # --- [CẬP NHẬT 3]: DỊCH LOẠI XE (Ví dụ: "CAR" -> "Xe ô tô") ---
            raw_vehicle_type = record.get('vehicle_type', '')
            ui_vehicle_name = raw_vehicle_type
            
            try:
                enum_vehicle = TrafficVehicleType[raw_vehicle_type]
                ui_vehicle_name = VehicleRegistry.get_name(enum_vehicle)
            except KeyError:
                pass # Bỏ qua nếu mã xe lạ, giữ nguyên tiếng Anh

            # Gán dữ liệu (đã dịch) lên Bảng
            self.table.setItem(row_idx, 0, stt_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(time_str))
            self.table.setItem(row_idx, 2, QTableWidgetItem(ui_error_name))
            self.table.setItem(row_idx, 3, QTableWidgetItem(ui_vehicle_name))
            self.table.setItem(row_idx, 4, QTableWidgetItem(record.get('lane_id', '')))
            
            raw_lane = record.get('lane_id', '')
            ui_lane = raw_lane if (raw_lane and raw_lane != "Ngoài làn") else "-"

            lane_item = QTableWidgetItem(ui_lane)
            lane_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, 4, lane_item)

            plate_item = QTableWidgetItem(record.get('license_plate', ''))
            font = QFont()
            font.setBold(True)
            plate_item.setFont(font)
            plate_item.setForeground(QBrush(QColor("#f39c12"))) 
            self.table.setItem(row_idx, 5, plate_item)

        self.table.blockSignals(False)
        self.lbl_page.setText(f"Trang {current_page} / {max(1, total_pages)}")

    def _on_row_selected(self):
        selected_items = self.table.selectedItems()
        if not selected_items: return
        
        # Lấy item đầu tiên của dòng được chọn (chính là ô STT)
        first_col_item = self.table.item(selected_items[0].row(), 0)
        
        # Moi dữ liệu ẩn ra và phát sóng
        record_data = first_col_item.data(Qt.ItemDataRole.UserRole)
        if record_data:
            app_broker.violation_row_selected.emit(record_data)

# --- END OF FILE ---