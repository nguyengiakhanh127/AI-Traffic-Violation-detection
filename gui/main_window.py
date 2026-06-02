# --- START OF FILE gui/main_window.py ---

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ==============================================================================

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QStackedWidget, QLabel, QButtonGroup
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QCursor

# Import UI Components chung
from gui.shared_components.collapsible_sidebar import CollapsibleSidebar
from gui.shared_components.custom_titlebar import CustomTitleBar
from utils import paths  # [CẬP NHẬT]: Dùng file paths.py của bạn cho chuyên nghiệp

# Import Tab 2: Config Builder
from gui.features.config_builder.builder_view import ConfigBuilderView

# [CẬP NHẬT LỚN]: Import Database và Tab 3 (Reviewer)
from infrastructure.database_service import DatabaseService
from gui.features.violation_reviewer.reviewer_view import ReviewerView
from gui.features.violation_reviewer.reviewer_controller import ReviewerController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Traffic AI System")
        self.resize(1280, 720)
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.db_service = DatabaseService(port=3306)

        self._setup_ui()
        self._load_stylesheet()

    def _setup_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("MainWrapper")
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        self.body_layout = QHBoxLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)
        
        self._setup_sidebar()
        self._setup_workspace()

        self.main_layout.addLayout(self.body_layout)

    def _setup_sidebar(self):
        self.sidebar_widget = CollapsibleSidebar(self)
        
        sidebar_layout = QVBoxLayout(self.sidebar_widget)
        sidebar_layout.setContentsMargins(0, 20, 0, 0)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Tạo Group để quản lý 3 nút (Đảm bảo chỉ 1 nút sáng lên lúc click)
        self.tab_group = QButtonGroup(self)

        # TAB 1: Live Monitor
        self.btn_tab_live = self._create_sidebar_btn("   Live Monitor", "monitor.png")
        self.btn_tab_live.setChecked(True)
        self.tab_group.addButton(self.btn_tab_live, 0)

        # TAB 2: Experiment Tool (Config Builder)
        self.btn_tab_config = self._create_sidebar_btn("   Experiment Tool", "settings.png")
        self.tab_group.addButton(self.btn_tab_config, 1)

        # [CẬP NHẬT]: TAB 3: Violation Reviewer (Kiểm duyệt)
        # Giả định bạn có 1 icon tên là 'document.png' hoặc 'history.png' trong assets
        self.btn_tab_review = self._create_sidebar_btn("   Violation Review", "review.png") 
        self.tab_group.addButton(self.btn_tab_review, 2)

        # Thêm nút vào Sidebar
        sidebar_layout.addWidget(self.btn_tab_live)
        sidebar_layout.addWidget(self.btn_tab_config)
        sidebar_layout.addWidget(self.btn_tab_review)

        self.body_layout.addWidget(self.sidebar_widget)

    def _create_sidebar_btn(self, text: str, icon_name: str) -> QPushButton:
        """Hàm hỗ trợ tạo nút Sidebar cho code gọn gàng"""
        btn = QPushButton(text)
        icon_path = os.path.join(paths.ICONS_DIR, icon_name)
        
        # Nếu chưa có icon thì xài đỡ icon mặc định, tránh bị crash
        if os.path.exists(icon_path):
            btn.setIcon(QIcon(icon_path))
            
        btn.setIconSize(QSize(22, 22))
        btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn.setCheckable(True)
        return btn

    def _setup_workspace(self):
        self.stacked_workspace = QStackedWidget()
        
        # --- TAB 0: Live Monitor ---
        self.page_live = QLabel("Khu vực Live Monitor\n(Tính năng đang xây dựng)")
        self.page_live.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_live.setStyleSheet("color: #aaaaaa; font-size: 18px;")
        
        # --- TAB 1: Experiment Tool (Config Builder) ---
        self.page_config = ConfigBuilderView(self.db_service)

        # Nối dây sự kiện Fullscreen (Focus Mode)
        self.page_config.get_toolbar().toggle_fullscreen.connect(self._toggle_fullscreen)

        # --- TAB 2: Violation Reviewer (KIỂM DUYỆT) ---
        self.page_reviewer = ReviewerView()
        # Khởi tạo Controller điều phối màn hình này và giao DB cho nó
        self.reviewer_controller = ReviewerController(self.page_reviewer, self.db_service)

        # Thêm 3 trang vào StackedWidget
        self.stacked_workspace.addWidget(self.page_live)
        self.stacked_workspace.addWidget(self.page_config)
        self.stacked_workspace.addWidget(self.page_reviewer)

        # Nối dây chuyển tab khi bấm nút ở Sidebar
        self.tab_group.idToggled.connect(self._change_tab)
        
        self.body_layout.addWidget(self.stacked_workspace, stretch=1)

    def _change_tab(self, tab_id, checked):
        if checked:
            self.stacked_workspace.setCurrentIndex(tab_id)

    def _toggle_fullscreen(self):
        """Chế độ Tập trung (Focus Mode) dành riêng cho lúc Vẽ cấu hình"""
        self.is_focus_mode = getattr(self, 'is_focus_mode', False)
        
        if not self.is_focus_mode:
            self.title_bar.hide()
            self.sidebar_widget.hide()
            self.page_config.panel.hide() 
            self.showMaximized()
            self.is_focus_mode = True
        else:
            self.title_bar.show()
            self.sidebar_widget.show()
            self.page_config.panel.show()
            self.showNormal()
            self.is_focus_mode = False

    def _load_stylesheet(self):
        qss_path = os.path.join(current_dir, "app_style.qss")
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except Exception as e:
            print(f"Warning: Không thể tải CSS: {e}")
    def _seed_fake_data(self):
        """Bơm dữ liệu giả vào DB (Đã cập nhật theo cấu trúc Khóa Ngoại)"""
        if self.db_service.get_total_count() > 0:
            return 
            
        print("Đang tạo Camera và 50 dữ liệu vi phạm giả...")
        import random
        from datetime import datetime, timedelta

        # 1. TẠO CAMERA GIẢ TRƯỚC VÀ LẤY ID
        cam1_id = self.db_service.add_camera("CAM_TEST_NGA_TU_A", "Nguyễn Trãi", "Khuất Duy Tiến")
        cam2_id = self.db_service.add_camera("CAM_TEST_CAO_TOC", "Cao Tốc NB-LC", "Nút giao 23")
        camera_ids = [cam1_id, cam2_id] # Danh sách các ID hợp lệ để random

        # 2. TẠO VI PHẠM GIẢ GHÉP VỚI CAMERA_ID
        errors = ["DI_SAI_LAN", "DI_NGUOC_CHIEU", "DE_VACH_PHAN_LAN", "VUOT_DEN_DO"]
        vehicles = ["CAR", "MOTORCYCLE", "TRUCK", "BUS"]
        lanes = ["Làn 1", "Làn 2", "Làn 3"]
        
        now = datetime.now()
        
        for i in range(50):
            random_time = now - timedelta(hours=random.randint(0, 48), minutes=random.randint(0, 60))
            
            fake_data = {
                "camera_id": random.choice(camera_ids), # [QUAN TRỌNG]: Giờ là ID, không phải Name
                "timestamp": random_time.strftime("%Y-%m-%d %H:%M:%S"),
                "violation_code": random.choice(errors),
                "vehicle_type": random.choice(vehicles),
                "lane_id": random.choice(lanes),
                "license_plate": f"{random.randint(11, 99)}{random.choice(['A','B','C','D'])}-{random.randint(10000, 99999)}",
                "evidence_path": "" 
            }
            self.db_service.insert_violation(fake_data)
            
        print("✅ Bơm dữ liệu giả thành công!")
            
        print("✅ Bơm dữ liệu giả thành công! Hãy mở Tab Reviewer lên xem.")
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
