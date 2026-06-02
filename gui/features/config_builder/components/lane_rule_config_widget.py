# --- START OF FILE gui/features/config_builder/components/lane_rule_config_widget.py ---
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QMenu, QWidgetAction, QCheckBox

from utils.enums import TrafficVehicleType
from gui.features.config_builder.components.base_config_card import BaseConfigCard

# [CẬP NHẬT]: Import Trạm phát sóng
from gui.shared_components.event_broker import app_broker 

class LaneRuleConfigWidget(BaseConfigCard):
    def __init__(self, parent=None):
        super().__init__(title="Lane Rule", icon_name="rules.png", bg_color="#262c2d", parent=parent)
        self.old_id = ""
        self.allowed_vehicles = set()
        self._setup_content_ui()

    def _setup_content_ui(self):
        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 5, 0, 5)
        
        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("VD: 01")
        self.input_id.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444; padding: 4px;")
        self.input_id.textChanged.connect(self._on_data_changed)
        form_layout.addRow("ID:", self.input_id)
        
        self.btn_vehicles = QPushButton("Chọn loại xe...")
        self.btn_vehicles.setStyleSheet("background-color: #333; text-align: left; padding: 4px;")
        self._setup_vehicle_menu()
        form_layout.addRow("Allowed:", self.btn_vehicles)
        
        self.content_layout.addLayout(form_layout)

    def _setup_vehicle_menu(self):
        menu = QMenu(self)
        vehicle_types = [e for e in TrafficVehicleType if e != TrafficVehicleType.UNKNOWN]
        
        for v_type in vehicle_types:
            action = QWidgetAction(menu)
            checkbox = QCheckBox(v_type.name)
            checkbox.setStyleSheet("padding: 5px;")
            checkbox.toggled.connect(lambda checked, t=v_type: self._on_vehicle_toggled(checked, t))
            action.setDefaultWidget(checkbox)
            menu.addAction(action)
            
        self.btn_vehicles.setMenu(menu)

    def _on_vehicle_toggled(self, checked: bool, v_type: TrafficVehicleType):
        if checked:
            self.allowed_vehicles.add(v_type)
        else:
            self.allowed_vehicles.discard(v_type)
            
        if not self.allowed_vehicles:
            self.btn_vehicles.setText("Chọn loại xe...")
        else:
            names = [v.name for v in self.allowed_vehicles]
            self.btn_vehicles.setText(", ".join(names)[:18] + "...")
            
        self._on_data_changed()

    def _on_data_changed(self):
        new_id = self.input_id.text().strip()
        if new_id:
            # [CẬP NHẬT]: Phát sóng thay vì dùng custom signal
            app_broker.rule_updated.emit(self, self.old_id, new_id, set(self.allowed_vehicles))
            self.old_id = new_id

    def _on_delete_clicked(self):
        # [CẬP NHẬT]: Phát sóng
        app_broker.rule_updated.emit(self, self.old_id, "", set())
        self.request_delete.emit(self)