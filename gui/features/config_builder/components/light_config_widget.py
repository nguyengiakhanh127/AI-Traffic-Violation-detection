# --- START OF FILE gui/features/config_builder/components/light_config_widget.py ---
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QFrame
from PyQt6.QtGui import QIcon
from gui.shared_components.reference_combobox import ReferenceComboBox
from gui.features.config_builder.components.base_config_card import BaseConfigCard
from utils import paths

# [CẬP NHẬT]: Import Trạm phát sóng
from gui.shared_components.event_broker import app_broker 
import os

class LightConfigWidget(BaseConfigCard):
    def __init__(self, parent=None):
        super().__init__(title="Traffic Light", icon_name="traffic_light.png", bg_color="#2d2626", parent=parent)
        self.current_bbox_id = None
        self.current_stop_id = None
        self.current_right_id = None
        self._setup_content_ui()

    def _setup_content_ui(self):
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 5, 0, 5)
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("VD: 01")
        self.input_id.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
        form_layout.addRow("ID:", self.input_id)
        self.content_layout.addLayout(form_layout)

        bbox_layout = QHBoxLayout()
        self.lbl_bbox_status = QLabel("BBox: Trống")
        self.lbl_bbox_status.setStyleSheet("color: #d4a017;")
        self.combo_bbox = ReferenceComboBox(target_type="BBOXES", allow_manual=False)
        self.combo_bbox.setMinimumWidth(120)
        self.combo_bbox.currentIndexChanged.connect(self._on_bbox_index_changed)
        
        self.btn_draw_bbox = QPushButton()
        self.btn_draw_bbox.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "plus.png")))
        self.btn_draw_bbox.setFixedSize(26, 26)
        self.btn_draw_bbox.setStyleSheet("background-color: #ff6b6b; font-weight: bold; border-radius: 3px;")
        self.btn_draw_bbox.clicked.connect(self._on_draw_bbox_clicked)
        
        bbox_layout.addWidget(self.lbl_bbox_status)
        bbox_layout.addStretch()
        bbox_layout.addWidget(self.combo_bbox)
        bbox_layout.addWidget(self.btn_draw_bbox)
        
        self.content_layout.addWidget(self._create_separator())
        self.content_layout.addLayout(bbox_layout)

        stop_layout = QHBoxLayout()
        self.lbl_stop_status = QLabel("Stop: Trống")
        self.lbl_stop_status.setStyleSheet("color: #d4a017;")
        self.combo_stop = ReferenceComboBox(target_type="LINES", allow_manual=False)
        self.combo_stop.setMinimumWidth(120)
        self.combo_stop.currentIndexChanged.connect(self._on_stop_index_changed)

        self.btn_draw_stop = QPushButton()
        self.btn_draw_stop.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "plus.png")))
        self.btn_draw_stop.setFixedSize(26, 26)
        self.btn_draw_stop.setStyleSheet("background-color: #ff6b6b; font-weight: bold; border-radius: 3px;")
        # [CẬP NHẬT]: Phát sóng yêu cầu vẽ Line
        self.btn_draw_stop.clicked.connect(lambda: app_broker.request_draw_line.emit(self, "stop"))
        
        stop_layout.addWidget(self.lbl_stop_status)
        stop_layout.addStretch()
        stop_layout.addWidget(self.combo_stop)
        stop_layout.addWidget(self.btn_draw_stop)
        self.content_layout.addLayout(stop_layout)

        right_layout = QHBoxLayout()
        self.lbl_right_status = QLabel("Right: Trống")
        self.lbl_right_status.setStyleSheet("color: #d4a017;")
        self.combo_right = ReferenceComboBox(target_type="LINES", allow_manual=False)
        self.combo_right.setMinimumWidth(120)
        self.combo_right.currentIndexChanged.connect(self._on_right_index_changed)
        
        self.btn_draw_right = QPushButton()
        self.btn_draw_right.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "plus.png")))
        self.btn_draw_right.setFixedSize(26, 26)
        self.btn_draw_right.setStyleSheet("background-color: #ff6b6b; font-weight: bold; border-radius: 3px;")
        # [CẬP NHẬT]: Phát sóng yêu cầu vẽ Line
        self.btn_draw_right.clicked.connect(lambda: app_broker.request_draw_line.emit(self, "right"))
        
        right_layout.addWidget(self.lbl_right_status)
        right_layout.addStretch()
        right_layout.addWidget(self.combo_right)
        right_layout.addWidget(self.btn_draw_right)
        self.content_layout.addLayout(right_layout)

    def _create_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #444; max-height: 1px;")
        return line

    def _on_draw_bbox_clicked(self):
        self.lbl_bbox_status.setText("Đang vẽ...")
        self.btn_draw_bbox.setStyleSheet("background-color: #5cb85c; font-weight: bold;")
        # [CẬP NHẬT]: Phát sóng
        app_broker.request_draw_bbox.emit(self)

    def update_edges_data(self, role: str, entity_id: str):
        if role == "stop":
            idx = self.combo_stop.findText(entity_id)
            if idx >= 0: self.combo_stop.setCurrentIndex(idx)
        elif role == "right":
            idx = self.combo_right.findText(entity_id)
            if idx >= 0: self.combo_right.setCurrentIndex(idx)

    def update_bbox_data(self, entity_id: str):
        idx = self.combo_bbox.findText(entity_id)
        if idx >= 0: self.combo_bbox.setCurrentIndex(idx)

    def _on_bbox_index_changed(self, index: int):
        text = self.combo_bbox.itemText(index)
        if text and text != "Trống":
            self.current_bbox_id = text
            self.lbl_bbox_status.setText("Đã Link")
            self.lbl_bbox_status.setStyleSheet("color: #5cb85c;")
            self.btn_draw_bbox.setStyleSheet("background-color: #ff6b6b; font-weight: bold;")

    def _on_stop_index_changed(self, index: int):
        text = self.combo_stop.itemText(index)
        if text and text != "Trống":
            self.current_stop_id = text
            self.lbl_stop_status.setText("Đã Link")
            self.lbl_stop_status.setStyleSheet("color: #5cb85c;")
            self.btn_draw_stop.setStyleSheet("background-color: #ff6b6b; font-weight: bold;")

    def _on_right_index_changed(self, index: int):
        text = self.combo_right.itemText(index)
        if text and text != "Trống":
            self.current_right_id = text
            self.lbl_right_status.setText("Đã Link")
            self.lbl_right_status.setStyleSheet("color: #5cb85c;")
            self.btn_draw_right.setStyleSheet("background-color: #ff6b6b; font-weight: bold;")

    def update_registry_list(self, registry_data: dict):
        self.combo_bbox.update_registry(registry_data)
        self.combo_stop.update_registry(registry_data)
        self.combo_right.update_registry(registry_data)