import cv2
import time
import os
import logging
from datetime import datetime
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from ultralytics import YOLO
    import supervision as sv
    HAS_AI_LIBS = True
except ImportError:
    HAS_AI_LIBS = False

from core.vehicle import Vehicle
from services.detection_service import DetectionService
from services.violation_service import ViolationService

from utils import paths
logger = logging.getLogger("AIVisionThread")

class AIVisionThread(QThread):
    """
    Luồng (Thread) xử lý AI chạy nền thời gian thực.
    Đảm nhận việc đọc Video -> Chạy YOLO + ByteTrack -> Định tuyến và Duyệt luật -> Phát tín hiệu.
    """
    # Phát tín hiệu mang theo frame gốc và danh sách phương tiện đã được xử lý xong
    frame_processed = pyqtSignal(np.ndarray, list, object)
    video_info_ready = pyqtSignal(float, int) 
    playback_finished = pyqtSignal()

    def __init__(
        self, 
        detection_service: DetectionService, 
        violation_service: ViolationService,
        traffic_lights: list, 
        model_path: str = paths.VEHICLE_DETECTION_OPENVINO_MODEL,
        parent=None
    ):
        super().__init__(parent)
        self.detection_service = detection_service
        self.violation_service = violation_service
        self.traffic_lights = traffic_lights
        self.model_path = model_path
        
        self.video_path = ""
        self.is_playing = False
        self.is_paused = False
        self.cap = None
        self.delay = 0.03

        self.ai_enabled = False

    def load_video(self, filepath: str):
        self.video_path = filepath
        self.cap = cv2.VideoCapture(filepath)
        
        if self.cap.isOpened():
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.delay = 1.0 / fps if fps > 0 else 0.03
            
            # Báo thông số video ra ngoài Panel để cấu hình thanh tua
            self.video_info_ready.emit(fps, total_frames)
            
            # Đọc và hiển thị ngay frame đầu tiên làm hình nền tĩnh
            ret, frame = self.cap.read()
            if ret:
                self.frame_processed.emit(frame, [], None)
        else:
            logger.error("❌ Không thể mở tệp video để phân tích.")

    def run(self):
        """
        Vòng lặp chính. Tự động chuyển đổi giữa chế độ phát tĩnh (Cấu hình) 
        và phát quét luật (Giám sát AI). Có cơ chế tự động dọn rác bộ nhớ.
        """
        model = None
        tracker = None
        
        # CHỈ tải mô hình YOLO và bộ theo vết khi người dùng kích hoạt nút START AI
        if self.ai_enabled:
            if not HAS_AI_LIBS:
                logger.error("❌ Thất bại: Chưa cài đặt thư viện 'ultralytics' hoặc 'supervision'!")
                self.playback_finished.emit()
                return

            if not os.path.exists(self.model_path):
                logger.error(f"❌ Không tìm thấy tệp trọng số mô hình tại: {self.model_path}")
                self.playback_finished.emit()
                return

            logger.info(f"Đang khởi động mô hình YOLO từ: {self.model_path}...")
            model = YOLO(self.model_path)
            tracker = sv.ByteTrack()
            logger.info("✅ Động cơ AI đã sẵn sàng.")

        self.is_playing = True
        
        # Dùng khối try...finally để bảo vệ việc dọn rác ngay cả khi xảy ra lỗi đột ngột
        try:
            while self.is_playing and self.cap and self.cap.isOpened():
                if self.is_paused:
                    time.sleep(0.1)
                    continue

                ret, frame = self.cap.read()
                if ret:
                    current_time = datetime.now()

                    # CHẾ ĐỘ 1: PHÁT QUÉT LUẬT AI (Kích hoạt khi bấm nút START AI)
                    if self.ai_enabled and model is not None and tracker is not None:
                        # 1. Đẩy frame vào RingBuffer (Nén JPEG In-Memory ngầm trong này)
                        self.violation_service.video_buffer.push(frame)

                        # 2. Chạy YOLO (Bỏ tham số device="cpu" để tự động dùng GPU/NPU nếu có)
                        results = model(frame, verbose=False, conf=0.3)[0]
                        detections = sv.Detections.from_ultralytics(results)
                        tracked_detections = tracker.update_with_detections(detections)

                        # 3. Chuyển cho DetectionService xử lý (Truyền frame vào để nén ảnh tự động)
                        active_vehicles = self.detection_service.process_frame(frame, tracked_detections)

                        # [ĐÃ XÓA]: Đoạn mã gán `vehicle.first_frame = frame.copy()` cũ kỹ và tốn RAM. 
                        # Việc nén ảnh (First Seen) đã được DetectionService và VehicleManager làm tự động!

                        # 4. Kiểm tra Luật và kích hoạt lưu Bằng chứng (Non-blocking)
                        self.violation_service.inspect_and_log(active_vehicles, current_time, frame, self.traffic_lights)
                        
                        # 5. Phát tín hiệu mang theo frame gốc và dữ liệu xe đã xử lý để vẽ UI
                        self.frame_processed.emit(frame, active_vehicles, tracked_detections)
                    
                    # CHẾ ĐỘ 2: PHÁT VIDEO TĨNH PHỤC VỤ VẼ CẤU HÌNH (Mặc định khi mới nạp file)
                    else:
                        # Chỉ phát ảnh thô của camera, tốc độ cực nhanh và 0% tốn CPU cho AI
                        self.frame_processed.emit(frame, [], None)

                    time.sleep(self.delay)
                else:
                    self.is_playing = False
                    break
                    
        finally:
            self.is_playing = False
            
            # [CẬP NHẬT 3]: ÉP CHỜ TRƯỚC KHI DỌN DẸP BỘ NHỚ
            if hasattr(self.violation_service, 'video_buffer') and self.ai_enabled:
                self.violation_service.video_buffer.wait_for_export_finish(timeout_sec=10)
            
            if model is not None:
                del model
                model = None
            if tracker is not None:
                del tracker
                tracker = None
                
            if hasattr(self.violation_service, 'video_buffer'):
                self.violation_service.video_buffer.clear()
            
            if hasattr(self.violation_service, 'shutdown'):
                self.violation_service.shutdown()
                
            import gc
            gc.collect()
            
            logger.info("🧹 Luồng AI đã kết thúc. Đã dọn dẹp sạch sẽ bộ nhớ RAM.")
            self.playback_finished.emit()

    # =========================================================================
    # PHƯƠNG THỨC STOP (DỪNG LUỒNG CHỦ ĐỘNG TỪ GIAO DIỆN)
    # =========================================================================
    def stop(self):
        """Dừng luồng chủ động và dọn dẹp bộ nhớ"""
        self.is_playing = False
        self.is_paused = False
        
        self.wait()
        
        if self.cap:
            self.cap.release()
            self.cap = None
            
        if hasattr(self.violation_service, 'video_buffer'):
            self.violation_service.video_buffer.clear()
            
        import gc
        gc.collect()
        
        logger.info("🛑 Đã tắt luồng AI Vision Thread và giải phóng tài nguyên hệ thống.")

    def seek_frame(self, frame_index: int):
        """Hỗ trợ người dùng kéo thanh trượt tua video"""
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ret, frame = self.cap.read()
            if ret:
                # Khi tua, phát frame tĩnh không chạy AI để tránh giật lag
                self.frame_processed.emit(frame, [], None)

    def toggle_pause(self):
        self.is_paused = not self.is_paused