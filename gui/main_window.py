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
    QPushButton, QStackedWidget, QLabel, QButtonGroup, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QCursor, QCloseEvent

# Import UI Components chung
from gui.shared_components.collapsible_sidebar import CollapsibleSidebar
from gui.shared_components.custom_titlebar import CustomTitleBar
from utils import paths

# Import các Tab
from gui.features.config_builder.builder_view import ConfigBuilderView
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

        # Khởi tạo Database Facade (Sử dụng Connection Pool)
        self.db_service = DatabaseService(port=3306)

        self._setup_ui()
        self._load_stylesheet()
        
        # Uncomment dòng dưới nếu muốn tự động tạo dữ liệu mẫu khi DB trống
        # self._seed_fake_data()

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

        self.tab_group = QButtonGroup(self)

        # TAB 1: Live Monitor
        self.btn_tab_live = self._create_sidebar_btn("   Live Monitor", "monitor.png")
        self.btn_tab_live.setChecked(True)
        self.tab_group.addButton(self.btn_tab_live, 0)

        # TAB 2: Experiment Tool (Config Builder)
        self.btn_tab_config = self._create_sidebar_btn("   Experiment Tool", "settings.png")
        self.tab_group.addButton(self.btn_tab_config, 1)

        # TAB 3: Violation Reviewer (Kiểm duyệt)
        self.btn_tab_review = self._create_sidebar_btn("   Violation Review", "review.png") 
        self.tab_group.addButton(self.btn_tab_review, 2)

        sidebar_layout.addWidget(self.btn_tab_live)
        sidebar_layout.addWidget(self.btn_tab_config)
        sidebar_layout.addWidget(self.btn_tab_review)

        self.body_layout.addWidget(self.sidebar_widget)

    def _create_sidebar_btn(self, text: str, icon_name: str) -> QPushButton:
        btn = QPushButton(text)
        icon_path = os.path.join(paths.ICONS_DIR, icon_name)
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
        self.page_config.get_toolbar().toggle_fullscreen.connect(self._toggle_fullscreen)

        # --- TAB 2: Violation Reviewer (KIỂM DUYỆT) ---
        self.page_reviewer = ReviewerView()
        self.reviewer_controller = ReviewerController(self.page_reviewer, self.db_service)

        self.stacked_workspace.addWidget(self.page_live)
        self.stacked_workspace.addWidget(self.page_config)
        self.stacked_workspace.addWidget(self.page_reviewer)

        self.tab_group.idToggled.connect(self._change_tab)
        
        self.body_layout.addWidget(self.stacked_workspace, stretch=1)

    def _change_tab(self, tab_id, checked):
        if checked:
            self.stacked_workspace.setCurrentIndex(tab_id)

    def _toggle_fullscreen(self):
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
        """[VÁ LỖI]: Bơm dữ liệu giả vào DB sử dụng API chuẩn của Repositories"""
        if self.db_service.violations.get_total_count() > 0:
            return 
            
        print("Đang tạo Camera và 50 dữ liệu vi phạm giả...")
        import random
        from datetime import datetime, timedelta

        cam1_id = self.db_service.cameras.add("CAM_TEST_NGA_TU_A", "Nguyễn Trãi", "Khuất Duy Tiến")
        cam2_id = self.db_service.cameras.add("CAM_TEST_CAO_TOC", "Cao Tốc NB-LC", "Nút giao 23")
        camera_ids = [cam1_id, cam2_id] 

        errors = ["DI_SAI_LAN", "DI_NGUOC_CHIEU", "DE_VACH_PHAN_LAN", "VUOT_DEN_DO"]
        vehicles = ["CAR", "MOTORCYCLE", "TRUCK", "BUS"]
        lanes = ["Làn 1", "Làn 2", "Làn 3"]
        
        now = datetime.now()
        
        for i in range(50):
            random_time = now - timedelta(hours=random.randint(0, 48), minutes=random.randint(0, 60))
            
            self.db_service.violations.insert(
                camera_id=random.choice(camera_ids),
                thoi_gian=random_time.strftime("%Y-%m-%d %H:%M:%S"),
                ma_loi=random.choice(errors),
                loai_xe=random.choice(vehicles),
                lan_duong=random.choice(lanes),
                bien_so=f"{random.randint(11, 99)}{random.choice(['A','B','C','D'])}-{random.randint(10000, 99999)}",
                duong_dan=""
            )
            
        print("✅ Bơm dữ liệu giả thành công! Hãy mở Tab Reviewer lên xem.")

    # =========================================================================
    # QUẢN LÝ VÒNG ĐỜI ỨNG DỤNG (GRACEFUL SHUTDOWN)
    # =========================================================================
    def closeEvent(self, event: QCloseEvent):
        """
        Bắt sự kiện khi người dùng bấm dấu X hoặc ấn tắt phần mềm.
        Đảm bảo dọn dẹp các Thread ngầm và lưu nốt bằng chứng xuống đĩa.
        """
        # Nếu AI đang chạy, cảnh báo người dùng
        if hasattr(self.page_config, 'controller'):
            video_thread = self.page_config.controller.video_thread
            if video_thread and video_thread.is_playing:
                reply = QMessageBox.question(
                    self, 'Cảnh báo',
                    "Hệ thống AI đang giám sát. Bạn có chắc chắn muốn thoát?\n"
                    "Quá trình này có thể mất vài giây để lưu nốt các vi phạm cuối cùng.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self._shutdown_services(video_thread)
                    event.accept()
                else:
                    event.ignore()
                return

        # Nếu AI không chạy, chỉ cần tắt dịch vụ
        self._shutdown_services(None)
        event.accept()

    def _shutdown_services(self, video_thread):
        print("Đang tiến hành dọn dẹp hệ thống trước khi thoát...")
        
        # 1. Tắt AI Thread (nếu có)
        if video_thread:
            video_thread.stop()
            video_thread.wait() # Chờ AI Thread ngắt an toàn
            
        # 2. Tắt dịch vụ Video Export ngầm
        if hasattr(self.page_config, 'controller'):
            violation_service = self.page_config.controller.violation_service
            if hasattr(violation_service, 'video_buffer'):
                violation_service.video_buffer.clear()
            
            # Tắt dịch vụ Ghi ảnh ngầm
            if hasattr(violation_service, 'evidence_generator'):
                violation_service.evidence_generator.shutdown()
                
        print("✅ Ứng dụng đã được đóng an toàn.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

# --- END OF FILE gui/main_window.py ---