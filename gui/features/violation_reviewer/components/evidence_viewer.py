# --- START OF FILE gui/features/violation_reviewer/components/evidence_viewer.py ---

import os
import cv2
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QStackedWidget, QFrame, QGridLayout, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QIcon, QPainter, QColor

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
            
            /* CSS Mới cho Bảng thông tin (Trong suốt, Căn trái, Chữ trắng đậm) */
            #InfoTable { background-color: transparent; padding: 10px 0px; }
            #PropLabel { color: #ffffff; font-weight: bold; font-size: 14px; }
            #ValLabel { color: #ffffff; font-weight: bold; font-size: 14px; padding-left: 5px; }
            #ValPlate { color: #f39c12; font-weight: bold; font-size: 16px; padding-left: 5px; }
        """)    
        
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

        self.btn_tab_img.toggled.connect(lambda c: self.btn_tab_vid.setChecked(not c))
        self.btn_tab_vid.toggled.connect(lambda c: self.btn_tab_img.setChecked(not c))

        self.btn_approve = QPushButton("✅ DUYỆT")
        self.btn_reject = QPushButton("❌ HỦY BỎ")
        self.btn_print = QPushButton("🖨️ IN BIÊN BẢN")

        self.btn_approve.clicked.connect(lambda: app_broker.submit_approval_decision.emit(self.current_record_id, 1))
        self.btn_reject.clicked.connect(lambda: app_broker.submit_approval_decision.emit(self.current_record_id, -1))
        self.btn_print.clicked.connect(lambda: app_broker.request_print_ticket.emit(self.current_record_id))

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_tab_img)
        header_layout.addWidget(self.btn_tab_vid)
        layout.addLayout(header_layout)

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

        # =========================================================
        # [CẬP NHẬT YÊU CẦU]: BẢNG THÔNG TIN SỰ KIỆN (QGridLayout)
        # =========================================================
        self._build_info_table()
        layout.addWidget(self.info_table_widget)

        self.stacked_widget.currentChanged.connect(self._on_tab_changed)

        # Action Layout
        self.action_layout = QHBoxLayout()
        self.action_layout.setContentsMargins(0, 10, 0, 0)
        
        self.btn_approve.setStyleSheet("background-color: #5cb85c; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_reject.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_print.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; padding: 8px; border-radius: 4px;")
        self.btn_approve.hide()
        self.btn_reject.hide()
        self.btn_print.hide()

        self.action_layout.addWidget(self.btn_reject)
        self.action_layout.addWidget(self.btn_approve)
        self.action_layout.addWidget(self.btn_print)
        
        layout.addLayout(self.action_layout)

    def _build_info_table(self):
        """Khởi tạo bố cục Bảng Thông tin (Bảng chiếm 100% chiều ngang, Nội dung căn trái)"""
        self.info_table_widget = QWidget()
        self.info_table_widget.setObjectName("InfoTable")
        self.info_table_widget.setVisible(False) 

        # Dùng QVBoxLayout thay vì QHBoxLayout để Grid tự động bung rộng theo chiều ngang
        main_table_layout = QVBoxLayout(self.info_table_widget)
        main_table_layout.setContentsMargins(0, 10, 0, 10) # Bỏ lề trái/phải để chiếm sát mép

        # Khởi tạo Grid Layout
        grid = QGridLayout()
        grid.setSpacing(15) 
        
        self.val_labels = {}
        # Định nghĩa 6 dòng (Tên hiển thị nội bộ, Tên file Icon, ObjectName cho CSS)
        rows_def = [
            ("camera", "Camera", "thin_unfill_camera.png", "ValLabel"),
            ("time", "Thời gian phát hiện", "unfill_clock.png", "ValLabel"),
            ("warning", "Loại cảnh báo", "unfill_warning.png", "ValLabel"),
            ("vehicle", "Đối tượng", "unfill_car.png", "ValLabel"),
            ("lane", "Làn đường", "unfill_lane.png", "ValLabel"),
            ("plate", "Biển số", "unfill_license_plate.png", "ValPlate"),
        ]

        ICON_GRAY_COLOR = "#aaaaaa" 

        for i, (key, text, icon_file, obj_name) in enumerate(rows_def):
            prop_wrap = QWidget()
            prop_layout = QHBoxLayout(prop_wrap)
            prop_layout.setContentsMargins(0, 0, 0, 0) 
            prop_layout.setSpacing(10)
            
            prop_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            icon_path = os.path.join(paths.ICONS_DIR, icon_file)
            if os.path.exists(icon_path):
                # Tải ảnh gốc
                original_pixmap = QPixmap(icon_path).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                # Phủ màu xám
                gray_pixmap = self._colorize_icon(original_pixmap, ICON_GRAY_COLOR)
                
                icon_lbl = QLabel()
                icon_lbl.setPixmap(gray_pixmap)
                prop_layout.addWidget(icon_lbl)
            else:
                emoji = {"camera": "📷", "time": "⏱️", "warning": "⚠️", "vehicle": "🚗", "lane": "🛣️", "plate": "🔡"}.get(key, "🔹")
                lbl_emoji = QLabel(emoji)
                # Nếu không có icon ảnh, ép màu chữ của Emoji thành màu xám
                lbl_emoji.setStyleSheet(f"color: {ICON_GRAY_COLOR};")
                prop_layout.addWidget(lbl_emoji)
                
            lbl_prop = QLabel(f"{text}:")
            lbl_prop.setObjectName("PropLabel")
            prop_layout.addWidget(lbl_prop)
            
            grid.addWidget(prop_wrap, i, 0)
            
            lbl_val = QLabel("-")
            lbl_val.setObjectName(obj_name)
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            
            grid.addWidget(lbl_val, i, 1)
            self.val_labels[key] = lbl_val

        grid.setColumnMinimumWidth(0, 200) 
        grid.setColumnStretch(1, 1)

        main_table_layout.addLayout(grid)


    def _wire_broker(self):
        app_broker.violation_row_selected.connect(self.load_evidence)


    def load_evidence(self, record_data: dict):
        self.current_folder = record_data.get('duong_dan_bang_chung', '') 
        self.current_record_id = record_data.get('id') 

        raw_error_code = record_data.get('ma_loi_vi_pham', '') 
        ui_error_name = raw_error_code
        status = record_data.get('trang_thai_duyet', 0) 

        if status == 0: 
            self.btn_approve.show()
            self.btn_reject.show()
            self.btn_print.hide()
        elif status == 1: 
            self.btn_approve.hide()
            self.btn_reject.hide()
            self.btn_print.show()
        else: 
            self.btn_approve.hide()
            self.btn_reject.hide()
            self.btn_print.hide()

        for v_type in ViolationType:
            if ViolationRegistry.get_code(v_type) == raw_error_code:
                ui_error_name = ViolationRegistry.get_name(v_type)
                break

        raw_vehicle_type = record_data.get('loai_phuong_tien', '')
        ui_vehicle_name = raw_vehicle_type
        try:
            enum_vehicle = TrafficVehicleType[raw_vehicle_type]
            ui_vehicle_name = VehicleRegistry.get_name(enum_vehicle)
        except KeyError:
            pass

        raw_time = record_data.get('thoi_gian_vi_pham', '')
        time_str = raw_time.strftime("%d/%m/%Y - %H:%M:%S") if isinstance(raw_time, datetime) else str(raw_time)

        # ======================================================
        # [CẬP NHẬT 2]: Bơm dữ liệu vào Bảng Grid
        # ======================================================
        self.info_table_widget.setVisible(True)
        self.val_labels["camera"].setText(record_data.get('ten_camera', 'N/A'))
        self.val_labels["time"].setText(time_str)
        self.val_labels["warning"].setText(ui_error_name)
        self.val_labels["vehicle"].setText(ui_vehicle_name)
        
        lane_str = record_data.get('lan_duong', '')
        self.val_labels["lane"].setText(lane_str if lane_str else "Ngoài làn")
        self.val_labels["plate"].setText(record_data.get('bien_so_xe', 'Chưa rõ'))

        # ======================================================
        # XỬ LÝ LOAD ẢNH VÀ VIDEO TỪ Ổ CỨNG
        # ======================================================
        self.image_files.clear()
        self._stop_video()
        self.video_path = ""
        self.lbl_image_display.setText("Đang tải ảnh...")
        self.lbl_video_display.setText("Chưa tải video")

        if self.current_folder and os.path.exists(self.current_folder):
            for file in sorted(os.listdir(self.current_folder)):
                ext = file.lower()          
                filepath = os.path.join(self.current_folder, file)
                
                if ext.endswith(('.jpg', '.png', '.jpeg')):
                    self.image_files.append(filepath)
                elif ext.endswith(('.mp4', '.avi')):
                    self.video_path = filepath
                    
            if self.image_files:
                self.current_img_idx = 0
                self._show_current_image()
            else:
                self.lbl_image_display.setText("Không tìm thấy ảnh bằng chứng.")
                self.lbl_img_counter.setText("0 / 0")
                
            if self.video_path:
                self.cap = cv2.VideoCapture(self.video_path)
                self._next_video_frame() 
        else:
            self.lbl_image_display.setText("Thư mục bằng chứng không tồn tại hoặc đã bị xóa.")

        self.btn_tab_img.setChecked(True)
        self.stacked_widget.setCurrentIndex(0)


    # --- CÁC HÀM XỬ LÝ ẢNH/VIDEO GIỮ NGUYÊN (Không ảnh hưởng Database) ---
    def _change_image(self, direction: int):
        if not self.image_files: return
        self.current_img_idx += direction
        
        if self.current_img_idx >= len(self.image_files): self.current_img_idx = 0
        elif self.current_img_idx < 0: self.current_img_idx = len(self.image_files) - 1
        
        self._show_current_image()

    def _show_current_image(self):
        filepath = self.image_files[self.current_img_idx]
        pixmap = QPixmap(filepath)
        
        label_size = self.lbl_image_display.size()
        scaled_pixmap = pixmap.scaled(label_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.lbl_image_display.setPixmap(scaled_pixmap)
        self.lbl_img_counter.setText(f"{self.current_img_idx + 1} / {len(self.image_files)}")

    def _toggle_video(self):
        if not self.cap or not self.cap.isOpened():
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
                self._stop_video() 
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
        if index == 0: 
            self._stop_video()
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.image_files and self.stacked_widget.currentIndex() == 0:
            self._show_current_image()

    def _colorize_icon(self, pixmap: QPixmap, color_hex: str) -> QPixmap:
        """Hàm hỗ trợ đổi màu (phủ màu) cho Icon có nền trong suốt"""
        colored_pixmap = QPixmap(pixmap.size())
        colored_pixmap.fill(Qt.GlobalColor.transparent) # Giữ nền trong suốt
        
        painter = QPainter(colored_pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.drawPixmap(0, 0, pixmap)
        
        # Lấy lớp Alpha (độ trong suốt) của ảnh gốc làm mặt nạ
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(colored_pixmap.rect(), QColor(color_hex))
        painter.end()
        
        return colored_pixmap
# --- END OF FILE gui/features/violation_reviewer/components/evidence_viewer.py ---