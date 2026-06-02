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
    Đảm nhận việc đọc Video -> Chạy YOLO + ByteTrack -> Định tuyến và Duyệt luật -> Phát tín hiệu hiển thị lên GUI.
    """
    # Phát tín hiệu mang theo frame gốc và danh sách phương tiện đã được xử lý xong
    frame_processed = pyqtSignal(np.ndarray, list, object)
    video_info_ready = pyqtSignal(float, int) 
    playback_finished = pyqtSignal()

    def __init__(
        self, 
        detection_service: DetectionService, 
        violation_service: ViolationService,
        model_path: str = paths.MODEL_DIR,
        parent=None
    ):
        super().__init__(parent)
        self.detection_service = detection_service
        self.violation_service = violation_service
        self.model_path = model_path
        
        self.video_path = ""
        self.is_playing = False
        self.is_paused = False
        self.cap = None
        self.delay = 0.03 # Giãn cách frame theo FPS

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
        
        # [CẬP NHẬT AN TOÀN]: Dùng khối try...finally để bảo vệ việc dọn rác
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
                        self.violation_service.video_buffer.push(frame)

                        results = model(frame, 
                                        verbose=False,
                                        classes=[1,2,3,5],
                                        conf=0.4,
                                        device="cpu")[0]
                        detections = sv.Detections.from_ultralytics(results)
                        tracked_detections = tracker.update_with_detections(detections)

                        active_vehicles = self.detection_service.process_frame(frame, tracked_detections)

                        for vehicle in active_vehicles:
                            if vehicle.coordinate.age == 1 and vehicle.first_frame is None:
                                vehicle.first_frame = frame.copy()
                                vehicle.first_bbox = vehicle.current_bbox

                        self.violation_service.inspect_and_log(active_vehicles, current_time, frame)
                        
                        # Phát tín hiệu mang theo frame gốc và dữ liệu xe đã xử lý
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
            # =========================================================================
            # [BẮT BUỘC CHẠY]: GIẢI PHÓNG TOÀN BỘ BỘ NHỚ RAM KHI LUỒNG KẾT THÚC
            # =========================================================================
            self.is_playing = False
            
            # 1. Hủy đối tượng Model YOLO và Tracker để ép giải phóng RAM
            if model is not None:
                del model
                model = None
            if tracker is not None:
                del tracker
                tracker = None
                
            # 2. Xả sạch bộ đệm Video Ring Buffer (Giải phóng ngay 5.5 GB RAM nếu có)
            if hasattr(self.violation_service, 'video_buffer'):
                self.violation_service.video_buffer.clear()
                
            # 3. Ép Python kích hoạt Garbage Collector để dọn rác bộ nhớ ngay lập tức
            import gc
            gc.collect()
            
            logger.info("🧹 Luồng AI đã kết thúc. Đã dọn dẹp sạch sẽ bộ nhớ RAM.")
            self.playback_finished.emit()

    # =========================================================================
    # PHƯƠNG THỨC STOP (DỪNG LUỒNG CHỦ ĐỘNG TỪ GIAO DIỆN)
    # =========================================================================
    def stop(self):
        """Dừng luồng chủ động và dọn dẹp bộ nhớ"""
        # 1. Phát cờ tắt vòng lặp
        self.is_playing = False
        self.is_paused = False
        
        # 2. Đợi luồng ngầm dừng hẳn để đảm bảo an toàn bộ nhớ (Tránh lỗi SegFault)
        self.wait()
        
        # 3. Giải phóng Camera
        if self.cap:
            self.cap.release()
            self.cap = None
            
        # 4. Xả sạch bộ đệm Video Ring Buffer
        if hasattr(self.violation_service, 'video_buffer'):
            self.violation_service.video_buffer.clear()
            
        # 5. Triệu gọi trình dọn rác của Python
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
