# --- START OF FILE gui/features/config_builder/ai_vision_thread.py ---

import cv2
import time
import os
import logging
from datetime import datetime
import numpy as np
from typing import List, Optional
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from ultralytics import YOLO
    import supervision as sv
    HAS_AI_LIBS = True
except ImportError:
    HAS_AI_LIBS = False

from core.vehicle import Vehicle
from core.trafficlight import TrafficLight
from services.detection_service import DetectionService
from services.violation_service import ViolationService
from utils import paths

logger = logging.getLogger("AIVisionThread")

class AIVisionThread(QThread):
    """
    Luồng (Worker Thread) xử lý AI độc lập với giao diện.
    Đã được tái cấu trúc để đảm bảo tính an toàn Thread-Safety của PyQt6.
    """
    
    # [QUAN TRỌNG]: Tín hiệu truyền dữ liệu giữa các luồng.
    # ndarray (Frame), list (Danh sách Vehicle), object (Detections - Khuyến cáo sau này nên bóc tách thành DTO)
    frame_processed = pyqtSignal(np.ndarray, list, object)
    video_info_ready = pyqtSignal(float, int) 
    playback_finished = pyqtSignal()

    def __init__(
        self, 
        detection_service: DetectionService, 
        violation_service: ViolationService,
        traffic_lights: List[TrafficLight], 
        model_path: str = paths.VEHICLE_DETECTION_OPENVINO_MODEL,
        parent=None
    ):
        super().__init__(parent)
        self.detection_service = detection_service
        self.violation_service = violation_service
        self.traffic_lights = traffic_lights
        self.model_path = model_path
        
        self.video_path: str = ""
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.delay: float = 0.03

        self.ai_enabled: bool = False

    def load_video(self, filepath: str) -> None:
        self.video_path = filepath
        self.cap = cv2.VideoCapture(filepath)
        
        if self.cap.isOpened():
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.delay = 1.0 / fps if fps > 0 else 0.03
            
            self.video_info_ready.emit(fps, total_frames)
            
            ret, frame = self.cap.read()
            if ret:
                # Gửi bản COPY để tránh crash nếu GUI vẽ quá chậm
                self.frame_processed.emit(frame.copy(), [], None)
        else:
            logger.error("❌ Không thể mở tệp video để phân tích.")

    def run(self) -> None:
        model = None
        tracker = None
        
        if self.ai_enabled:
            if not HAS_AI_LIBS:
                logger.error("❌ Thất bại: Thiếu thư viện AI cốt lõi.")
                self.playback_finished.emit()
                return

            if not os.path.exists(self.model_path):
                logger.error(f"❌ Không tìm thấy trọng số AI tại: {self.model_path}")
                self.playback_finished.emit()
                return

            logger.info(f"Đang khởi tạo Engine AI (CPU Optimized)...")
            # Cấu hình ONNX/OpenVINO cần truyền tham số cấu trúc để tối ưu CPU.
            model = YOLO(self.model_path, task='detect')
            tracker = sv.ByteTrack()
            logger.info("✅ Động cơ AI đã sẵn sàng.")

        self.is_playing = True
        
        try:
            while self.is_playing and self.cap and self.cap.isOpened():
                if self.is_paused:
                    time.sleep(0.05)
                    continue

                ret, frame = self.cap.read()
                if ret:
                    current_time = datetime.now()

                    if self.ai_enabled and model is not None and tracker is not None:
                        # 1. Đẩy vào RingBuffer để xuất Video ngầm (Thread-safe)
                        if hasattr(self.violation_service, 'video_buffer'):
                            self.violation_service.video_buffer.push(frame)

                        # 2. Suy luận AI
                        results = model(frame, verbose=False, conf=0.3)[0]
                        detections = sv.Detections.from_ultralytics(results)
                        tracked_detections = tracker.update_with_detections(detections)

                        # 3. Phân tích Dịch vụ Không gian (Cập nhật Frame copy để lưu ảnh)
                        active_vehicles = self.detection_service.process_frame(frame, tracked_detections)

                        # 4. Kiểm tra Luật và kích hoạt lưu Bằng chứng (Toàn bộ là Non-blocking Async)
                        self.violation_service.inspect_and_log(active_vehicles, current_time, frame, self.traffic_lights)
                        
                        # [QUAN TRỌNG NHẤT]: Gửi bản COPY. Giao diện (VisualAnnotator) 
                        # sẽ vẽ trên ảnh này trong khi Luồng AI đã lấy frame tiếp theo.
                        self.frame_processed.emit(frame.copy(), active_vehicles, tracked_detections)
                    
                    else:
                        self.frame_processed.emit(frame.copy(), [], None)

                    time.sleep(self.delay)
                else:
                    self.is_playing = False
                    break
                    
        finally:
            self._cleanup_resources(model, tracker)

    def _cleanup_resources(self, model, tracker) -> None:
        self.is_playing = False
        
        # Đợi các tiến trình ghi I/O hoàn tất trước khi tắt hẳn
        if hasattr(self.violation_service, 'video_buffer') and self.ai_enabled:
            try:
                self.violation_service.video_buffer.wait_for_export_finish(timeout_sec=5)
            except Exception as e:
                logger.error(f"Lỗi khi chờ xuất video: {e}")
        
        # Chủ động ép dọn dẹp các mảng Tensor trên CPU
        if model is not None: del model
        if tracker is not None: del tracker
            
        if hasattr(self.violation_service, 'video_buffer'):
            self.violation_service.video_buffer.clear()
            
        import gc
        gc.collect()
        
        logger.info("🧹 Luồng AI đã đóng và giải phóng RAM thành công.")
        self.playback_finished.emit()

    def stop(self) -> None:
        """Kích hoạt cờ dừng và trả quyền cho Main Thread (Non-blocking)"""
        if self.is_playing:
            logger.info("Đang yêu cầu dừng AI Vision Thread...")
            self.is_playing = False
            self.is_paused = False
            
            # Không dùng self.wait() ở đây vì nó sẽ block UI. 
            # Thread sẽ tự động tắt khi vòng lặp run() kết thúc do cờ is_playing=False.

    def seek_frame(self, frame_index: int) -> None:
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ret, frame = self.cap.read()
            if ret:
                self.frame_processed.emit(frame.copy(), [], None)

    def toggle_pause(self) -> None:
        self.is_paused = not self.is_paused

# --- END OF FILE gui/features/config_builder/ai_vision_thread.py ---