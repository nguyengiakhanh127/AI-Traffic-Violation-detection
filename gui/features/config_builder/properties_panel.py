# --- START OF FILE gui/features/config_builder/properties_panel.py ---
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QFrame, QMenu, QScrollArea,
    QSlider, QComboBox, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap
import os

from gui.shared_components.collapsible_box import CollapsibleBox
from gui.features.config_builder.components.lane_config_widget import LaneConfigWidget
from gui.features.config_builder.components.zone_config_widget import ZoneConfigWidget
from gui.features.config_builder.components.light_config_widget import LightConfigWidget
from gui.features.config_builder.components.lane_rule_config_widget import LaneRuleConfigWidget
from gui.features.config_builder.components.base_config_card import BaseConfigCard
from gui.shared_components.event_broker import *

from utils import paths
class PropertiesPanel(QWidget):
    # =========================================================================
    # [CẬP NHẬT]: CHỈ GIỮ LẠI CÁC TÍN HIỆU CỦA RIÊNG PANEL (Không làm trung gian nữa)
    # =========================================================================
    media_load_requested = pyqtSignal(str)  
    play_pause_requested = pyqtSignal()     
    seek_requested = pyqtSignal(int)        
    export_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    start_ai_requested = pyqtSignal()
    import_requested = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setObjectName("RightPanel")
        self.icon_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons")
        
        self.current_registry_data = {
            "POLYGONS": [], "BBOXES": [], "LINES": [], "RULES": []
        }
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. KHU VỰC CAMERA VÀ VIDEO
        camera_group = QFrame()
        camera_group.setStyleSheet("QFrame { background-color: #2d2d2d; border-radius: 5px; }")
        cam_layout = QVBoxLayout(camera_group)
        cam_layout.setContentsMargins(10, 10, 10, 10)
        
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(8)
        
        lbl_cam_icon = QLabel()
        lbl_cam_icon.setPixmap(QPixmap(os.path.join(self.icon_dir, "camera.png")).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lbl_cam_icon.setFixedWidth(24)
        
        # 1. KHỞI TẠO COMBOBOX
        self.combo_cam_select = QComboBox()
        self.combo_cam_select.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444; padding: 4px; color: white;")
        self.combo_cam_select.setToolTip("Chọn Camera để áp dụng cấu hình này")
        
        # 2. KHỞI TẠO NÚT "IMPORT"
        self.btn_import = QPushButton()
        self.btn_import.setIcon(QIcon(os.path.join(self.icon_dir, "folder.png"))) 
        self.btn_import.setFixedSize(26, 26)
        self.btn_import.setToolTip("Tải cấu hình (Import) từ Cơ sở dữ liệu")
        self.btn_import.setStyleSheet("background-color: #2b5797; color: white; border-radius: 3px;")
        self.btn_import.clicked.connect(self._on_import_clicked)


        # 3. KHỞI TẠO NÚT BROWSE (BỊ THIẾU LÚC NÃY)
        self.btn_browse = QPushButton()
        self.btn_browse.setIcon(QIcon(os.path.join(self.icon_dir, "folder.png"))) 
        self.btn_browse.setIconSize(QSize(16, 16))
        self.btn_browse.setFixedWidth(35)
        self.btn_browse.setToolTip("Chọn tệp Video/Ảnh để phân tích")
        self.btn_browse.clicked.connect(self._on_browse_clicked)
        
        # 4. THÊM TẤT CẢ VÀO LAYOUT THEO ĐÚNG THỨ TỰ
        row1_layout.addWidget(lbl_cam_icon)
        row1_layout.addWidget(self.combo_cam_select, stretch=1)
        row1_layout.addWidget(self.btn_import)
        row1_layout.addWidget(self.btn_browse)
        
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("FPS:"))
        self.lbl_fps = QLabel("N/A")
        self.lbl_fps.setStyleSheet("font-weight: bold;")
        self.lbl_frame_count = QLabel("0 / 0")
        self.lbl_frame_count.setStyleSheet("color: #aaa;")
        row2_layout.addWidget(self.lbl_fps)
        row2_layout.addStretch()
        row2_layout.addWidget(self.lbl_frame_count)
        
        row3_layout = QHBoxLayout()
        self.btn_play = QPushButton()
        self.btn_play.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "play.png")))
        self.btn_play.setFixedSize(30, 24)
        self.btn_play.setStyleSheet("background-color: #f29c22; border-radius: 3px; font-weight: bold; color: white;")
        self.btn_play.clicked.connect(self.play_pause_requested.emit)
        
        self.slider_video = QSlider(Qt.Orientation.Horizontal)
        self.slider_video.setEnabled(False) 
        self.slider_video.sliderMoved.connect(self.seek_requested.emit) 
        
        row3_layout.addWidget(self.btn_play)
        row3_layout.addWidget(self.slider_video)

        cam_layout.addLayout(row1_layout)
        cam_layout.addLayout(row2_layout)
        cam_layout.addLayout(row3_layout)
        main_layout.addWidget(camera_group)

        # 2. KHU VỰC CẤU HÌNH ĐỐI TƯỢNG
        self.config_box = CollapsibleBox("Cấu hình đối tượng")
        inner_layout = QVBoxLayout()
        inner_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #444; border-radius: 3px; background-color: #1e1e1e; min-height: 200px; }")
        
        self.object_list_widget = QWidget()
        self.object_list_layout = QVBoxLayout(self.object_list_widget)
        self.object_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.object_list_widget)
        
        action_layout = QHBoxLayout()
        self.btn_add_obj = QPushButton()
        self.btn_add_obj.setIcon(QIcon(os.path.join(self.icon_dir, "plus.png")))
        self.btn_add_obj.setStyleSheet("background-color: #2b5797; font-weight: bold; padding: 5px;")
        self.btn_add_obj.clicked.connect(self._show_add_menu)
        
        self.btn_del_all = QPushButton("")
        self.btn_del_all.setIcon(QIcon(os.path.join(self.icon_dir, "trash_can.png")))
        self.btn_del_all.setStyleSheet("background-color: #666; font-weight: bold; padding: 5px;")
        self.btn_del_all.clicked.connect(self._clear_all_cards)
        
        action_layout.addWidget(self.btn_add_obj)
        action_layout.addWidget(self.btn_del_all)

        inner_layout.addLayout(action_layout)
        inner_layout.addWidget(self.scroll_area)
        self.config_box.set_content_layout(inner_layout)

        main_layout.addWidget(self.config_box)
        main_layout.addStretch()

        # 3. ACTION BUTTONS (Footer)
        bottom_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Làm mới dữ liệu")
        self.btn_reset.setStyleSheet("background-color: #d9534f; font-weight: bold; padding: 10px; border-radius: 4px;")
        self.btn_reset.clicked.connect(self.reset_requested.emit)
        
        self.btn_export = QPushButton("Xuất JSON")
        self.btn_export.setStyleSheet("background-color: #007acc; font-weight: bold; padding: 10px; border-radius: 4px;")
        self.btn_export.clicked.connect(self.export_requested.emit)
        
        bottom_layout.addWidget(self.btn_reset, stretch=1)
        bottom_layout.addWidget(self.btn_export, stretch=2)
        main_layout.addLayout(bottom_layout)

        self.chk_save_db = QCheckBox("Lưu vi phạm vào Cơ sở dữ liệu")
        self.chk_save_db.setStyleSheet("color: #f39c12; font-weight: bold; margin-bottom: 5px;")
        self.chk_save_db.setChecked(False) # Mặc định TẮT (Chế độ an toàn)
        self.chk_save_db.toggled.connect(app_broker.toggle_db_logging.emit)
        
        main_layout.addWidget(self.chk_save_db)

        # Nút Start AI (Giữ nguyên)
        self.btn_start_ai = QPushButton("Chạy phát hiện đối tượng")
        self.btn_start_ai.setStyleSheet("""
            QPushButton { background-color: #f69926; color: black; font-weight: bold; padding: 12px; border-radius: 4px; font-size: 13px; }
            QPushButton:hover { background-color: #e17e26; }
        """)
        self.btn_start_ai.clicked.connect(self.start_ai_requested.emit)
        main_layout.addWidget(self.btn_start_ai)

    def _on_import_clicked(self):
        cam_id = self.combo_cam_select.currentData()
        if cam_id:
            self.import_requested.emit(cam_id)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Lưu ý", "Vui lòng chọn Camera trước khi tải cấu hình!")

    def _on_browse_clicked(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Chọn File Media", "", "Media Files (*.mp4 *.avi *.mkv *.jpg *.png);;All Files (*)")
        if filepath:
            #self.input_cam_name.setText(os.path.basename(filepath))
            self.media_load_requested.emit(filepath)

    def _show_add_menu(self):
        menu = QMenu(self)
        menu.addAction("Thêm Làn đường", lambda: self._add_card("Lane"))
        menu.addAction("Thêm Vùng cấm", lambda: self._add_card("Zone"))
        menu.addAction("Thêm Đèn tín hiệu", lambda: self._add_card("Light"))
        menu.addAction("Thêm Luật Làn", lambda: self._add_card("Rule"))
        menu.exec(self.btn_add_obj.mapToGlobal(self.btn_add_obj.rect().bottomLeft()))

    def _add_card(self, obj_type: str):
        card = None
        if obj_type == "Lane": card = LaneConfigWidget()
        elif obj_type == "Zone": card = ZoneConfigWidget()
        elif obj_type == "Light": card = LightConfigWidget()
        elif obj_type == "Rule": card = LaneRuleConfigWidget()
        
        if card:
            card.request_delete.connect(self._remove_card)
            self.object_list_layout.addWidget(card)

            if hasattr(self, 'current_registry_data') and hasattr(card, 'update_registry_list'):
                card.update_registry_list(self.current_registry_data)

            self.config_box.update_content_height()

    def _remove_card(self, card_widget):
        self.object_list_layout.removeWidget(card_widget)
        card_widget.deleteLater()

        QTimer.singleShot(10, self.config_box.update_content_height)


    def _clear_all_cards(self):
        while self.object_list_layout.count():
            child = self.object_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        BaseConfigCard.reset_counters()
        QTimer.singleShot(10, self.config_box.update_content_height)

    def update_video_info(self, fps: float, total_frames: int):
        self.lbl_fps.setText(f"{fps:.1f}")
        self.slider_video.setRange(0, total_frames)
        self.slider_video.setEnabled(True)
        self.lbl_frame_count.setText(f"0 / {total_frames}")

    def update_video_progress(self, current_frame: int):
        self.slider_video.blockSignals(True)
        self.slider_video.setValue(current_frame)
        self.slider_video.blockSignals(False)
        self.lbl_frame_count.setText(f"{current_frame} / {self.slider_video.maximum()}")

    def broadcast_registry_update(self, registry_data: dict): 
        self.current_registry_data = registry_data
        for i in range(self.object_list_layout.count()):
            widget = self.object_list_layout.itemAt(i).widget()
            if hasattr(widget, 'update_registry_list'):
                widget.update_registry_list(registry_data)

    def reset_form(self):
        self.combo_cam_select.setCurrentIndex(-1) 
        
        self._clear_all_cards()