from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QFrame
from PyQt6.QtGui import QIcon
from gui.shared_components.reference_combobox import ReferenceComboBox
from gui.features.config_builder.components.base_config_card import BaseConfigCard
from utils import paths

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
        self.input_id.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444; padding: 4px;")
        form_layout.addRow("ID:", self.input_id)
        self.content_layout.addLayout(form_layout)

        # ==========================================
        # 1. HÀNG: BBOX (HỘP ĐÈN)
        # ==========================================
        bbox_layout = QHBoxLayout()
        self.lbl_bbox_status = QLabel("Trống")
        self.lbl_bbox_status.setStyleSheet("color: #d4a017;")
        
        self.combo_bbox = ReferenceComboBox(target_type="BBOXES", allow_manual=False)
        self.combo_bbox.setMinimumWidth(110)
        self.combo_bbox.currentIndexChanged.connect(self._on_bbox_index_changed)
        
        # [THÊM]: Hover Highlight cho Bbox
        self.combo_bbox.reference_hovered.connect(app_broker.request_highlight_polygon.emit)
        self.combo_bbox.reference_cleared.connect(app_broker.clear_highlight_polygon.emit)
        
        self.btn_action_bbox = self._create_action_button()
        self.btn_action_bbox.clicked.connect(lambda: self._on_action_clicked("BBOX"))
        
        bbox_layout.addWidget(QLabel("BBox:"))
        bbox_layout.addWidget(self.lbl_bbox_status)
        bbox_layout.addStretch()
        bbox_layout.addWidget(self.combo_bbox)
        bbox_layout.addWidget(self.btn_action_bbox)
        
        self.content_layout.addWidget(self._create_separator())
        self.content_layout.addLayout(bbox_layout)

        # ==========================================
        # 2. HÀNG: STOP LINE (VẠCH DỪNG)
        # ==========================================
        stop_layout = QHBoxLayout()
        self.lbl_stop_status = QLabel("Trống")
        self.lbl_stop_status.setStyleSheet("color: #d4a017;")
        
        self.combo_stop = ReferenceComboBox(target_type="LINES", allow_manual=False)
        self.combo_stop.setMinimumWidth(110)
        self.combo_stop.currentIndexChanged.connect(self._on_stop_index_changed)

        # [THÊM]: Hover Highlight cho Line
        self.combo_stop.reference_hovered.connect(app_broker.request_highlight_polygon.emit)
        self.combo_stop.reference_cleared.connect(app_broker.clear_highlight_polygon.emit)

        self.btn_action_stop = self._create_action_button()
        self.btn_action_stop.clicked.connect(lambda: self._on_action_clicked("STOP"))
        
        stop_layout.addWidget(QLabel("Stop:"))
        stop_layout.addWidget(self.lbl_stop_status)
        stop_layout.addStretch()
        stop_layout.addWidget(self.combo_stop)
        stop_layout.addWidget(self.btn_action_stop)
        self.content_layout.addLayout(stop_layout)

        # ==========================================
        # 3. HÀNG: RIGHT TURN LINE (VẠCH RẼ PHẢI - Tùy chọn)
        # ==========================================
        right_layout = QHBoxLayout()
        self.lbl_right_status = QLabel("Trống")
        self.lbl_right_status.setStyleSheet("color: #d4a017;")
        
        self.combo_right = ReferenceComboBox(target_type="LINES", allow_manual=False)
        self.combo_right.setMinimumWidth(110)
        self.combo_right.currentIndexChanged.connect(self._on_right_index_changed)
        
        # [THÊM]: Hover Highlight cho Line
        self.combo_right.reference_hovered.connect(app_broker.request_highlight_polygon.emit)
        self.combo_right.reference_cleared.connect(app_broker.clear_highlight_polygon.emit)

        self.btn_action_right = self._create_action_button()
        self.btn_action_right.clicked.connect(lambda: self._on_action_clicked("RIGHT"))
        
        right_layout.addWidget(QLabel("Right:"))
        right_layout.addWidget(self.lbl_right_status)
        right_layout.addStretch()
        right_layout.addWidget(self.combo_right)
        right_layout.addWidget(self.btn_action_right)
        self.content_layout.addLayout(right_layout)

    def _create_action_button(self):
        """Hàm hỗ trợ tạo nút Vẽ màu Đỏ"""
        btn = QPushButton()
        btn.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "plus.png")))
        btn.setFixedSize(26, 26)
        btn.setStyleSheet("background-color: #ff6b6b; font-weight: bold; border-radius: 3px;")
        return btn

    def _create_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("background-color: #444; max-height: 1px; margin: 4px 0px;")
        return line

    # =====================================================================
    # LOGIC XỬ LÝ CLICK NÚT (VẼ / XÓA)
    # =====================================================================
    def _on_action_clicked(self, role: str):
        obj_id = None
        btn = None
        lbl = None
        
        # Ánh xạ theo role
        if role == "BBOX":
            obj_id, btn, lbl = self.current_bbox_id, self.btn_action_bbox, self.lbl_bbox_status
        elif role == "STOP":
            obj_id, btn, lbl = self.current_stop_id, self.btn_action_stop, self.lbl_stop_status
        elif role == "RIGHT":
            obj_id, btn, lbl = self.current_right_id, self.btn_action_right, self.lbl_right_status

        # 1. NẾU CHƯA CÓ HÌNH -> RA LỆNH VẼ
        if not obj_id or obj_id == "Trống":
            lbl.setText("Đang vẽ...")
            btn.setStyleSheet("background-color: #5cb85c; font-weight: bold; border-radius: 3px;")
            
            # Yêu cầu Canvas đổi Tool tương ứng
            if role == "BBOX":
                app_broker.request_draw_bbox.emit(self)
            else:
                app_broker.request_draw_line.emit(self, role.lower())
                
        # 2. NẾU ĐÃ CÓ HÌNH -> RA LỆNH XÓA (Thùng rác)
        else:
            app_broker.request_delete_entity.emit(obj_id) # Phát sóng tiêu diệt
            
            # Gỡ bỏ liên kết trên UI
            if role == "BBOX":
                self.current_bbox_id = None
                self.combo_bbox.setCurrentIndex(0)
            elif role == "STOP":
                self.current_stop_id = None
                self.combo_stop.setCurrentIndex(0)
            elif role == "RIGHT":
                self.current_right_id = None
                self.combo_right.setCurrentIndex(0)
                
            # Phục hồi giao diện nút bấm thành dấu [+] màu Đỏ nhạt
            lbl.setText("Trống")
            lbl.setStyleSheet("color: #d4a017;")
            btn.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "plus.png")))
            btn.setStyleSheet("background-color: #ff6b6b; font-weight: bold; border-radius: 3px;")


    # =====================================================================
    # LOGIC UPDATE TỪ CANVAS / BROKER TRẢ VỀ
    # =====================================================================
    def update_edges_data(self, role: str, entity_id: str):
        """Được gọi bởi WorkspaceManager khi vẽ xong Line"""
        if role == "stop":
            idx = self.combo_stop.findText(entity_id)
            if idx >= 0: self.combo_stop.setCurrentIndex(idx)
        elif role == "right":
            idx = self.combo_right.findText(entity_id)
            if idx >= 0: self.combo_right.setCurrentIndex(idx)

    def update_bbox_data(self, entity_id: str):
        """Được gọi bởi WorkspaceManager khi vẽ xong BBox"""
        idx = self.combo_bbox.findText(entity_id)
        if idx >= 0: self.combo_bbox.setCurrentIndex(idx)

    # =====================================================================
    # LOGIC ĐỔI TRẠNG THÁI COMBOBOX
    # =====================================================================
    def _on_bbox_index_changed(self, index: int):
        text = self.combo_bbox.itemText(index)
        if text and text not in ["Trống", "✏ Tạo thủ công (Draw New)"]:
            self.current_bbox_id = text
            self.lbl_bbox_status.setText("Đã tham chiếu")
            self.lbl_bbox_status.setStyleSheet("color: #5cb85c;")
            self.btn_action_bbox.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "delete.png")))
            self.btn_action_bbox.setStyleSheet("#d9534f; font-weight: bold; border-radius: 3px;")

    def _on_stop_index_changed(self, index: int):
        text = self.combo_stop.itemText(index)
        if text and text not in ["Trống", "✏ Tạo thủ công (Draw New)"]:
            self.current_stop_id = text
            self.lbl_stop_status.setText("Đã tham chiếu")
            self.lbl_stop_status.setStyleSheet("color: #5cb85c;")
            self.btn_action_stop.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "delete.png")))
            self.btn_action_stop.setStyleSheet("#d9534f; font-weight: bold; border-radius: 3px;")

    def _on_right_index_changed(self, index: int):
        text = self.combo_right.itemText(index)
        if text and text not in ["Trống", "✏ Tạo thủ công (Draw New)"]:
            self.current_right_id = text
            self.lbl_right_status.setText("Đã tham chiếu")
            self.lbl_right_status.setStyleSheet("color: #5cb85c;")
            self.btn_action_right.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "delete.png")))
            self.btn_action_right.setStyleSheet("font-weight: bold; border-radius: 3px;")

    def update_registry_list(self, registry_data: dict):
        self.combo_bbox.update_registry(registry_data)
        self.combo_stop.update_registry(registry_data)
        self.combo_right.update_registry(registry_data)