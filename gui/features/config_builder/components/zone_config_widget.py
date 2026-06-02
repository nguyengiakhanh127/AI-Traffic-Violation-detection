# --- START OF FILE gui/features/config_builder/components/zone_config_widget.py ---
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QComboBox, QSpinBox)
from PyQt6.QtGui import QIcon
from utils.enums import TrafficZoneType
from gui.shared_components.reference_combobox import ReferenceComboBox
from gui.features.config_builder.components.base_config_card import BaseConfigCard
from utils import paths

# [CẬP NHẬT]: Import Trạm phát sóng
from gui.shared_components.event_broker import app_broker 
import os

class ZoneConfigWidget(BaseConfigCard):
    def __init__(self, parent=None):
        super().__init__(title="Traffic Zone", icon_name="danger.png", bg_color="#2a2d2a", parent=parent)
        self.current_obj_id = None
        self._setup_content_ui()

    def _setup_content_ui(self):
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 5, 0, 5)
        
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("EX: 01")
        self.input_id.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        form_layout.addRow("ID:", self.input_id)

        self.combo_type = QComboBox()
        self.combo_type.addItems([e.name for e in TrafficZoneType])
        self.combo_type.setStyleSheet("background-color: #333;")
        form_layout.addRow("Type:", self.combo_type)

        hours_layout = QHBoxLayout()
        self.spin_start_hour = QSpinBox()
        self.spin_start_hour.setRange(0, 23)
        self.spin_start_hour.setValue(6)
        self.spin_start_hour.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        
        self.spin_end_hour = QSpinBox()
        self.spin_end_hour.setRange(0, 23)
        self.spin_end_hour.setValue(22)
        self.spin_end_hour.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        
        hours_layout.addWidget(self.spin_start_hour)
        hours_layout.addWidget(QLabel("đến"))
        hours_layout.addWidget(self.spin_end_hour)
        form_layout.addRow("Giờ cấm:", hours_layout)

        self.combo_days = QComboBox()
        self.combo_days.addItems(["Không cấm theo ngày", "Cấm ngày chẵn", "Cấm ngày lẻ"])
        self.combo_days.setStyleSheet("background-color: #333;")
        form_layout.addRow("Ngày cấm:", self.combo_days)
        self.content_layout.addLayout(form_layout)

        edges_layout = QHBoxLayout()
        self.lbl_edges_count = QLabel("Status: Trống")
        self.lbl_edges_count.setStyleSheet("color: #d4a017;") 
        
        self.combo_ref = ReferenceComboBox(target_type="POLYGONS", allow_manual=False)
        self.combo_ref.setMinimumWidth(120)
        
        # [CẬP NHẬT]: Nối tín hiệu Hover
        self.combo_ref.reference_hovered.connect(app_broker.request_highlight_polygon.emit)
        self.combo_ref.reference_cleared.connect(app_broker.clear_highlight_polygon.emit)
        self.combo_ref.currentIndexChanged.connect(self._on_combo_index_changed)

        self.btn_draw = QPushButton()
        self.btn_draw.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "plus.png")))
        self.btn_draw.setFixedSize(26, 26)
        self.btn_draw.setStyleSheet("background-color: #4CAF50; font-weight: bold; border-radius: 3px;")
        self.btn_draw.clicked.connect(self._on_draw_clicked)
        
        edges_layout.addWidget(self.lbl_edges_count)
        edges_layout.addStretch()
        edges_layout.addWidget(self.combo_ref)
        edges_layout.addWidget(self.btn_draw)
        self.content_layout.addLayout(edges_layout)

    def update_registry_list(self, registry_data: dict):
        self.combo_ref.update_registry(registry_data)
    
    def _on_draw_clicked(self):
        self.lbl_edges_count.setText("Đang vẽ...")
        self.btn_draw.setStyleSheet("background-color: #5cb85c; font-weight: bold;")
        # [CẬP NHẬT]: Phát sóng
        app_broker.request_draw_polygon.emit(self)

    def _on_combo_index_changed(self, index: int):
        selected_text = self.combo_ref.itemText(index)
        if selected_text and selected_text != "Trống":
            self.current_obj_id = selected_text
            self.btn_draw.setStyleSheet("background-color: #4CAF50; font-weight: bold;")
            self.lbl_edges_count.setText("Chọn đối tượng")
            self.lbl_edges_count.setStyleSheet("color: #5cb85c;")