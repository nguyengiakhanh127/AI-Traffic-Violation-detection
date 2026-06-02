# --- START OF FILE gui/features/config_builder/components/lane_config_widget.py ---
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QComboBox
from PyQt6.QtGui import QIcon

from utils.enums import TrafficLineType
from gui.shared_components.reference_combobox import ReferenceComboBox
from gui.features.config_builder.components.base_config_card import BaseConfigCard
from utils import paths

# [CẬP NHẬT]: Import Trạm phát sóng
from gui.shared_components.event_broker import app_broker 
import os

class LaneConfigWidget(BaseConfigCard):
    def __init__(self, parent=None):
        super().__init__(
            title="Traffic Lane", icon_name="road.png", bg_color="#2a2a2d", parent=parent
        )
        self.current_obj_id = None
        self._setup_content_ui()

    def _setup_content_ui(self):
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 5, 0, 5)
        
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("VD: 01")
        self.input_id.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444; padding: 4px;")
        form_layout.addRow("ID:", self.input_id)
        
        self.combo_rule_ref = ReferenceComboBox(target_type="RULES", allow_manual=False)
        form_layout.addRow("Lane Rule:", self.combo_rule_ref)
        
        self.content_layout.addLayout(form_layout)

        edges_layout = QHBoxLayout()
        self.lbl_edges_count = QLabel("Status: Trống")
        self.lbl_edges_count.setStyleSheet("color: #d4a017;") 
        
        self.combo_ref = ReferenceComboBox(target_type="POLYGONS", allow_manual=False)
        self.combo_ref.setMinimumWidth(120)
        
        # [CẬP NHẬT]: Nối thẳng tín hiệu Hover vào Broker
        self.combo_ref.reference_hovered.connect(app_broker.request_highlight_polygon.emit)
        self.combo_ref.reference_cleared.connect(app_broker.clear_highlight_polygon.emit)
        self.combo_ref.currentIndexChanged.connect(self._on_combo_index_changed)

        self.btn_draw = QPushButton()
        self.btn_draw.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "plus.png")))
        self.btn_draw.setFixedSize(26, 26)
        self.btn_draw.setStyleSheet("background-color: #007acc; font-weight: bold; border-radius: 3px;")
        self.btn_draw.clicked.connect(self._on_draw_clicked)
        
        edges_layout.addWidget(self.lbl_edges_count)
        edges_layout.addStretch()
        edges_layout.addWidget(self.combo_ref)
        edges_layout.addWidget(self.btn_draw)
        self.content_layout.addLayout(edges_layout)

        self.sub_edges_container = QWidget()
        self.sub_edges_layout = QVBoxLayout(self.sub_edges_container)
        self.sub_edges_layout.setContentsMargins(0, 5, 0, 0)
        self.sub_edges_layout.setSpacing(5)
        self.sub_edges_container.hide() 
        self.content_layout.addWidget(self.sub_edges_container)

    def _on_draw_clicked(self):
        self.lbl_edges_count.setText("Đang vẽ...")
        self.btn_draw.setStyleSheet("background-color: #5cb85c; font-weight: bold;")
        self._clear_sub_edges()
        # [CẬP NHẬT]: Phát sóng yêu cầu vẽ
        app_broker.request_draw_polygon.emit(self)

    def _on_combo_index_changed(self, index: int):
        selected_text = self.combo_ref.itemText(index)
        if selected_text and selected_text != "Trống":
            self.current_obj_id = selected_text
            self.btn_draw.setStyleSheet("background-color: #007acc; font-weight: bold;")
            # [CẬP NHẬT]: Phát sóng lấy số lượng cạnh
            app_broker.request_edge_count.emit(self, selected_text)

    def update_registry_list(self, registry_data: dict):
        self.combo_ref.update_registry(registry_data)
        self.combo_rule_ref.update_registry(registry_data)

    def _clear_sub_edges(self):
        while self.sub_edges_layout.count():
            child = self.sub_edges_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.sub_edges_container.hide()

    def build_sub_edges_ui(self, edge_count: int):
        self._clear_sub_edges()
        self.lbl_edges_count.setText(f"Đã Link ({edge_count} cạnh)")
        self.lbl_edges_count.setStyleSheet("color: #5cb85c;")
        
        self.sub_edge_combos = []
        for i in range(edge_count):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(5, 2, 5, 2)
            
            lbl_edge = QLabel(f"Edge {i+1}:")
            lbl_edge.setFixedWidth(50)
            
            combo_type = QComboBox()
            combo_type.addItems([e.name for e in TrafficLineType])
            combo_type.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444;")
            self.sub_edge_combos.append(combo_type)
            
            row_layout.addWidget(lbl_edge)
            row_layout.addWidget(combo_type)
            
            # [CẬP NHẬT]: Phát sóng highlight cạnh con
            row_widget.enterEvent = lambda event, idx=i: app_broker.request_highlight_sub_edge.emit(self.current_obj_id, idx)
            row_widget.leaveEvent = lambda event, idx=i: app_broker.clear_highlight_sub_edge.emit(self.current_obj_id, idx)
            
            self.sub_edges_layout.addWidget(row_widget)
            
        self.sub_edges_container.show()