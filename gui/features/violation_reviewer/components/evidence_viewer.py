# --- START OF FILE gui/features/violation_reviewer/components/evidence_viewer.py ---
import os
import cv2
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QStackedWidget, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QIcon

from gui.shared_components.event_broker import app_broker

from core.rules import ViolationRegistry, VehicleRegistry
from utils.enums import TrafficVehicleType, ViolationType
from utils import paths
from datetime import datetime
class EvidenceViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EvidenceViewer")
        self.setStyleSheet("""
            #EvidenceViewer { background-color: #1a1a1c; border-radius: 8px; }
            QLabel { color: #aaaaaa; }
            QPushButton.TabBtn { 
                background-color: transparent; color: #aaaaaa; border: none; 
                font-weight: bold; font-size: 14px; padding: 5px 15px; border-bottom: 2px solid transparent;
            }
            QPushButton.TabBtn:checked { color: #f39c12; border-bottom: 2px solid #f39c12; }
            QFrame#DisplayFrame { background-color: #000000; border-radius: 5px; }
        """)
        
        # Biến trạng thái
        self.current_folder = ""
        self.current_record_id = None
        self.image_files = []
        self.current_img_idx = 0
        
        self.video_path = ""
        self.cap = None
        self.video_timer = QTimer()
        self.video_timer.timeout.connect(self._next_video_frame)
        self.is_playing = False

        self._setup_ui()
        self._wire_broker()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)

        # 1. HEADER (Tiêu đề + Nút Tab Hình ảnh/Video)
        header_layout = QHBoxLayout()
        title = QLabel("Chi tiết sự kiện")
        title.setStyleSheet("color: white; font-weight: bold; font-size: 14px;")
        
        self.btn_tab_img = QPushButton(" Hình ảnh")
        self.btn_tab_img.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "image.png")))
        self.btn_tab_img.setProperty("class", "TabBtn")
        self.btn_tab_img.setCheckable(True)
        self.btn_tab_img.setChecked(True)
        self.btn_tab_img.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        
        self.btn_tab_vid = QPushButton("  Video")
        self.btn_tab_vid.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "video.png")))
        self.btn_tab_vid.setProperty("class", "TabBtn")
        self.btn_tab_vid.setCheckable(True)
        self.btn_tab_vid.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        # Đảm bảo chỉ 1 tab được sáng lên
        self.btn_tab_img.toggled.connect(lambda c: self.btn_tab_vid.setChecked(not c))
        self.btn_tab_vid.toggled.connect(lambda c: self.btn_tab_img.setChecked(not c))

        self.btn_approve = QPushButton("✅ DUYỆT & LẬP BIÊN BẢN")
        self.btn_reject = QPushButton("❌ HỦY BỎ (Sai sót/Xe ưu tiên)")
        self.btn_print = QPushButton("🖨️ IN BIÊN BẢN PHẠT NGUỘI")

        self.btn_approve.clicked.connect(lambda: app_broker.submit_approval_decision.emit(self.current_record_id, 1))
        self.btn_reject.clicked.connect(lambda: app_broker.submit_approval_decision.emit(self.current_record_id, -1))
        self.btn_print.clicked.connect(lambda: app_broker.request_print_ticket.emit(self.current_record_id))

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_tab_img)
        header_layout.addWidget(self.btn_tab_vid)
        layout.addLayout(header_layout)

        # 2. KHU VỰC TRÌNH CHIẾU (Stacked Widget: Chứa 2 màn hình xếp chồng nhau)
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("DisplayFrame")
        self.stacked_widget.setMinimumHeight(350)
        
        # --- MÀN HÌNH 1: XEM ẢNH ---
        page_image = QWidget()
        page_img_layout = QVBoxLayout(page_image)
        page_img_layout.setContentsMargins(0,0,0,0)
        
        self.lbl_image_display = QLabel("Chưa chọn sự kiện")
        self.lbl_image_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image_display.setStyleSheet("background-color: black; border-radius: 5px;")
        
        img_controls = QHBoxLayout()
        self.btn_prev_img = QPushButton(" Trước")
        self.btn_prev_img.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "thin_back.png")))
        self.btn_next_img = QPushButton("Tiếp  ")
        self.btn_next_img.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "thin_next.png")))
        self.btn_next_img.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.lbl_img_counter = QLabel("0 / 0")
        
        for btn in [self.btn_prev_img, self.btn_next_img]:
            btn.setStyleSheet("background-color: #333; color: white; padding: 5px 15px; border-radius: 3px;")
        
        self.btn_prev_img.clicked.connect(lambda: self._change_image(-1))
        self.btn_next_img.clicked.connect(lambda: self._change_image(1))
        
        img_controls.addStretch()
        img_controls.addWidget(self.btn_prev_img)
        img_controls.addWidget(self.lbl_img_counter)
        img_controls.addWidget(self.btn_next_img)
        img_controls.addStretch()
        
        page_img_layout.addWidget(self.lbl_image_display, stretch=1)
        page_img_layout.addLayout(img_controls)
        self.stacked_widget.addWidget(page_image)

        # --- MÀN HÌNH 2: XEM VIDEO ---
        page_video = QWidget()
        page_vid_layout = QVBoxLayout(page_video)
        page_vid_layout.setContentsMargins(0,0,0,0)
        
        self.lbl_video_display = QLabel("Video không khả dụng")
        self.lbl_video_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video_display.setStyleSheet("background-color: black; border-radius: 5px;")
        
        vid_controls = QHBoxLayout()
        self.btn_play_pause = QPushButton("Phát")
        self.btn_play_pause.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "play.png")))
        self.btn_play_pause.setStyleSheet("background-color: #f39c12; color: #111; font-weight: bold; padding: 5px 15px; border-radius: 3px;")
        self.btn_play_pause.clicked.connect(self._toggle_video)
        
        vid_controls.addStretch()
        vid_controls.addWidget(self.btn_play_pause)
        vid_controls.addStretch()
        
        page_vid_layout.addWidget(self.lbl_video_display, stretch=1)
        page_vid_layout.addLayout(vid_controls)
        self.stacked_widget.addWidget(page_video)

        layout.addWidget(self.stacked_widget, stretch=1)

        # 3. THÔNG TIN CHI TIẾT (Footer)
        self.lbl_details = QLabel("Vui lòng chọn một bản ghi bên danh sách để xem chi tiết.")
        self.lbl_details.setWordWrap(True)
        self.lbl_details.setStyleSheet("color: white; padding-top: 10px;")
        layout.addWidget(self.lbl_details)

        # Khi chuyển tab, tự động dừng video nếu đang phát
        self.stacked_widget.currentChanged.connect(self._on_tab_changed)

        self.action_layout = QHBoxLayout()
        self.action_layout.setContentsMargins(0, 15, 0, 0)
        
        # Nút cho Trạng thái: CHỜ DUYỆT
        self.btn_approve = QPushButton("DUYỆT BẢN GHI")
        self.btn_approve.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "true.png")))
        self.btn_approve.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        
        self.btn_reject = QPushButton("HỦY BỎ BẢN GHI")
        self.btn_reject.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "false.png")))
        self.btn_reject.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        
        # Nút cho Trạng thái: ĐÃ DUYỆT
        self.btn_print = QPushButton("🖨️ IN BIÊN BẢN PHẠT NGUỘI")
        self.btn_print.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_print.hide() # Mặc định ẩn

        self.action_layout.addWidget(self.btn_reject)
        self.action_layout.addWidget(self.btn_approve)
        self.action_layout.addWidget(self.btn_print)
        
        layout.addLayout(self.action_layout)

    def _wire_broker(self):
        """Móc tai nghe vào trạm phát sóng để lắng nghe khi có dòng dữ liệu được chọn"""
        app_broker.violation_row_selected.connect(self.load_evidence)

    def load_evidence(self, record_data: dict):
        self.current_folder = record_data.get('evidence_path', '')
        self.current_record_id = record_data.get('id') 

        # --- [CẬP NHẬT 2]: Dịch Dữ liệu y như bên Table ---
        raw_error_code = record_data.get('violation_code', '')
        ui_error_name = raw_error_code
        status = record_data.get('is_reviewed', 0)

        if status == 0: # Chờ duyệt
            self.btn_approve.show()
            self.btn_reject.show()
            self.btn_print.hide()
        elif status == 1: # Đã duyệt
            self.btn_approve.hide()
            self.btn_reject.hide()
            self.btn_print.show()
        else: # Đã hủy (-1)
            self.btn_approve.hide()
            self.btn_reject.hide()
            self.btn_print.hide()

        for v_type in ViolationType:
            if ViolationRegistry.get_code(v_type) == raw_error_code:
                ui_error_name = ViolationRegistry.get_name(v_type)
                break

        raw_vehicle_type = record_data.get('vehicle_type', '')
        ui_vehicle_name = raw_vehicle_type
        try:
            enum_vehicle = TrafficVehicleType[raw_vehicle_type]
            ui_vehicle_name = VehicleRegistry.get_name(enum_vehicle)
        except KeyError:
            pass

        raw_time = record_data.get('timestamp', '')
        time_str = raw_time.strftime("%d/%m/%Y %H:%M:%S") if isinstance(raw_time, datetime) else str(raw_time)

        info_text = (
            f"<b>Biển số:</b> <span style='color:#f39c12; font-size: 16px;'>{record_data.get('license_plate')}</span><br>"
            f"<b>Lỗi vi phạm:</b> {ui_error_name}<br>"
            f"<b>Đối tượng:</b> {ui_vehicle_name}<br>"
            f"<b>Thời gian:</b> {time_str}<br>"  # <--- Dùng time_str đã format
            f"<b>Camera:</b> {record_data.get('camera_name')}"
        )
        self.lbl_details.setText(info_text)


        # 2. Dọn dẹp rác cũ
        self.image_files.clear()
        self._stop_video()
        self.video_path = ""
        self.lbl_image_display.setText("Đang tải ảnh...")
        self.lbl_video_display.setText("Chưa tải video")

        # 3. Quét thư mục tìm Ảnh và Video
        if self.current_folder and os.path.exists(self.current_folder):
            for file in sorted(os.listdir(self.current_folder)):
                ext = file.lower()
                filepath = os.path.join(self.current_folder, file)
                
                if ext.endswith(('.jpg', '.png', '.jpeg')):
                    self.image_files.append(filepath)
                elif ext.endswith(('.mp4', '.avi')):
                    self.video_path = filepath
                    
            # Hiển thị ảnh đầu tiên
            if self.image_files:
                self.current_img_idx = 0
                self._show_current_image()
            else:
                self.lbl_image_display.setText("Không tìm thấy ảnh bằng chứng.")
                self.lbl_img_counter.setText("0 / 0")
                
            # Mở sắn Video nếu có
            if self.video_path:
                self.cap = cv2.VideoCapture(self.video_path)
                self._next_video_frame() # Chụp 1 khung hình hiển thị tĩnh
        else:
            self.lbl_image_display.setText("Thư mục bằng chứng không tồn tại.")

        # Tự động nhảy về Tab Ảnh
        self.btn_tab_img.setChecked(True)
        self.stacked_widget.setCurrentIndex(0)

    # --- LOGIC XỬ LÝ ẢNH ---
    def _change_image(self, direction: int):
        if not self.image_files: return
        self.current_img_idx += direction
        
        # Kéo xoay vòng (Loop)
        if self.current_img_idx >= len(self.image_files): self.current_img_idx = 0
        elif self.current_img_idx < 0: self.current_img_idx = len(self.image_files) - 1
        
        self._show_current_image()

    def _show_current_image(self):
        filepath = self.image_files[self.current_img_idx]
        pixmap = QPixmap(filepath)
        
        # Lấy kích thước hiện tại của Label để co giãn ảnh cho vừa, giữ đúng tỷ lệ
        label_size = self.lbl_image_display.size()
        scaled_pixmap = pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.lbl_image_display.setPixmap(scaled_pixmap)
        self.lbl_img_counter.setText(f"{self.current_img_idx + 1} / {len(self.image_files)}")

    # --- LOGIC XỬ LÝ VIDEO BẰNG QTIMER ---
    def _toggle_video(self):
        if not self.cap or not self.cap.isOpened():
            # Nếu chạy hết rồi thì mở lại từ đầu
            if self.video_path:
                self.cap = cv2.VideoCapture(self.video_path)
            else: return

        self.is_playing = not self.is_playing
        if self.is_playing:
            self.btn_play_pause.setText("⏸ Tạm dừng")
            self.btn_play_pause.setStyleSheet("background-color: #d9534f; color: white;")
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            interval = int(1000 / fps) if fps > 0 else 33
            self.video_timer.start(interval)
        else:
            self.btn_play_pause.setText("▶ Phát")
            self.btn_play_pause.setStyleSheet("background-color: #f39c12; color: #111;")
            self.video_timer.stop()

    def _next_video_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = frame.shape
                img = QImage(frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                pixmap = QPixmap.fromImage(img)
                
                label_size = self.lbl_video_display.size()
                self.lbl_video_display.setPixmap(pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self._stop_video() # Hết video
                self.lbl_video_display.setText("Video đã kết thúc.")

    def _stop_video(self):
        self.is_playing = False
        self.video_timer.stop()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.btn_play_pause.setText("▶ Phát (Lại)")
        self.btn_play_pause.setStyleSheet("background-color: #f39c12; color: #111;")

    def _on_tab_changed(self, index: int):
        if index == 0: # Đổi sang tab Ảnh -> Tắt video đang chạy
            self._stop_video()
            
    def resizeEvent(self, event):
        """Giữ ảnh khỏi vỡ khi user kéo to nhỏ cửa sổ ứng dụng"""
        super().resizeEvent(event)
        if self.image_files and self.stacked_widget.currentIndex() == 0:
            self._show_current_image()

    