# --- START OF FILE services/violation_service.py ---

import os
import logging
import numpy as np
import cv2
import threading
from queue import Queue, Full
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass

from core.vehicle import Vehicle
from core.engine import ViolationEvent, InspectionContext 
from core.trafficlight import TrafficLight
from infrastructure.evidence_generator import EvidenceGenerator
from infrastructure.database_service import DatabaseService

# Import mô hình ALPR mới thiết kế
from infrastructure.ai_adapters.alpr.plate_recognizer import LicensePlateRecognizer

logger = logging.getLogger("ViolationService")

@dataclass
class ALPRTask:
    """Cấu trúc dữ liệu chứa nhiệm vụ đọc biển số chờ được xử lý"""
    record_id: int
    vehicle_crop: np.ndarray
    event_folder: str
    timestamp_str: str

class ViolationService:
    """
    Dịch vụ điều phối: Kiểm tra vi phạm và kích hoạt chuỗi ghi nhận bằng chứng.
    Hỗ trợ xử lý I/O và ALPR bất đồng bộ qua các Hàng đợi (Queues) và Worker Threads.
    """
    def __init__(
        self, 
        rule_engine, 
        record_manager, 
        video_buffer, 
        lane_manager, 
        zone_manager, 
        evidence_generator: EvidenceGenerator, 
        db_service: Optional[DatabaseService] = None, 
        alpr_service: Optional[LicensePlateRecognizer] = None
    ):
        self.rule_engine = rule_engine
        self.record_manager = record_manager
        self.video_buffer = video_buffer
        self.lane_manager = lane_manager
        self.zone_manager = zone_manager
        self.evidence_generator = evidence_generator 
        self.db_service = db_service 
        self.alpr_service = alpr_service
        
        self.current_camera_id: Optional[int] = None 
        
        # =========================================================
        # [CẬP NHẬT KIẾN TRÚC]: Hàng đợi và Worker Thread cho ALPR
        # =========================================================
        self._alpr_queue: Queue[ALPRTask] = Queue(maxsize=50) # Chứa tối đa 50 xe vi phạm chờ đọc biển
        self._is_running: bool = True
        
        # Chỉ bật luồng OCR nếu mô hình đã được cung cấp (tiêm) vào Service
        if self.alpr_service is not None:
            self._alpr_worker_thread = threading.Thread(
                target=self._async_alpr_worker,
                name="ALPRWorkerThread",
                daemon=True
            )
            self._alpr_worker_thread.start()
            logger.info("✅ Luồng ngầm đọc biển số (ALPR Thread) đã khởi động.")

    def inspect_and_log(
        self, active_vehicles: List[Vehicle], current_time: datetime, frame: np.ndarray, 
        traffic_lights: Optional[List[TrafficLight]] = None
    ) -> List[ViolationEvent]:

        new_violations_this_frame = []
        traffic_lights = traffic_lights or []

        for light in traffic_lights:
            light.update_state(frame)

        for vehicle in active_vehicles:
            if not vehicle.is_stable:
                continue
                
            current_lane = self.lane_manager.get_lane_at_position(vehicle.routing_point)
            matched_zones = self.zone_manager.get_zones_at_position(vehicle.routing_point)

            context = InspectionContext(
                lane=current_lane, 
                zones=matched_zones, 
                traffic_lights=traffic_lights, 
                current_time=current_time
            )
            
            violations = self.rule_engine.inspect_vehicle(vehicle, context)

            if violations:
                for event in violations:
                    log_result = self.record_manager.log_violation(vehicle, event, current_time)
                    
                    if log_result:
                        new_record, evidence_dir = log_result
                        logger.info(f"🚨 [PHÁT HIỆN]: {event.error_name} - Xe {vehicle.vehicle_type.name} ID:{vehicle.id}")
                        new_violations_this_frame.append(event)
                        
                        vehicle.add_violation_frame(event.error_name, frame, vehicle.current_bbox)
                        
                        self._trigger_evidence_chain(vehicle, event, current_time, current_lane, evidence_dir)
                            
        return new_violations_this_frame

    def _trigger_evidence_chain(self, vehicle: Vehicle, event: ViolationEvent, 
                                current_time: datetime, current_lane, event_folder: str) -> None:
        """Kích hoạt chuỗi lưu trữ bằng cách ném nhiệm vụ vào các Hàng đợi (Non-blocking)"""
        try:
            insert_id = None
            if self.db_service and self.current_camera_id:
                lane_str = current_lane.lane_id if current_lane else "Ngoài làn"
                
                # 1. Ghi DB lấy ID
                insert_id = self.db_service.violations.insert(
                    camera_id=self.current_camera_id,
                    thoi_gian=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    ma_loi=event.error_name,
                    loai_xe=vehicle.vehicle_type.value, 
                    lan_duong=lane_str,
                    bien_so="", 
                    duong_dan=event_folder
                )
            
            file_timestamp = current_time.strftime("%Hh%Mm%Ss_%f")[:-3]

            # 2. Kích hoạt xuất Video (Ném vào Queue)
            video_filepath = os.path.join(event_folder, f"{file_timestamp}_video.mp4")
            self.video_buffer.trigger_export(video_filepath)

            # 3. Kích hoạt xuất Ảnh Full (Ném vào Queue)
            self.evidence_generator.export_evidence_images(
                vehicle=vehicle, 
                violation_code=event.error_name,
                img_dir=event_folder, 
                timestamp_str=file_timestamp
            )

            # =========================================================
            # [CẬP NHẬT]: 4. Kích hoạt luồng ALPR (Đẩy vào Queue)
            # =========================================================
            if self.alpr_service and insert_id is not None:
                # Trích xuất ảnh xe bằng CPU (Rất nhanh)
                vehicle_crop = self.evidence_generator.extract_crop_for_ocr(vehicle, event.error_name)
                
                if vehicle_crop is not None:
                    task = ALPRTask(
                        record_id=insert_id,
                        vehicle_crop=vehicle_crop,
                        event_folder=event_folder,
                        timestamp_str=file_timestamp
                    )
                    try:
                        self._alpr_queue.put_nowait(task)
                    except Full:
                        logger.warning(f"⚠️ Hàng đợi ALPR đã đầy! Bỏ qua đọc biển số cho ID {insert_id}")

        except Exception as e:
            logger.error(f"❌ Lỗi khi thực thi chuỗi sinh bằng chứng: {e}")

    # =========================================================
    # HÀM XỬ LÝ CHẠY NGẦM CHO ALPR
    # =========================================================
    def _async_alpr_worker(self) -> None:
        """Worker Thread: Liên tục lấy ảnh từ Hàng đợi để giải mã biển số"""
        while self._is_running:
            task: ALPRTask = self._alpr_queue.get()
            
            if task is None: # Tín hiệu đóng luồng (Poison Pill)
                break
                
            try:
                # 1. Gọi mô hình xử lý
                plate_text, drawn_img = self.alpr_service.recognize(task.vehicle_crop)
                
                # 2. Lưu ảnh biển số ra thư mục bằng chứng (I/O)
                if drawn_img is not None and task.event_folder:
                    plate_filepath = os.path.join(task.event_folder, f"{task.timestamp_str}_5_plate_crop.jpg")
                    cv2.imwrite(plate_filepath, drawn_img)
                
                # 3. Cập nhật biển số vào Database thông qua Connection Pool
                if self.db_service:
                    self.db_service.violations.update_license_plate(task.record_id, plate_text)
                    
                    if plate_text != "Không xác định":
                        logger.info(f"🔎 [ALPR]: ID {task.record_id} -> {plate_text}")
                    
            except Exception as e:
                logger.error(f"❌ Lỗi nội bộ trong luồng ALPR: {e}")
            finally:
                self._alpr_queue.task_done()

    def shutdown(self) -> None:
        """Đóng các luồng an toàn khi tắt phần mềm"""
        self._is_running = False
        
        # Bắn Poison Pill để đóng luồng ALPR
        if hasattr(self, '_alpr_worker_thread') and self._alpr_worker_thread.is_alive():
            logger.info("⏳ Đang chờ ALPR xử lý nốt biển số cuối cùng...")
            self._alpr_queue.put(None) 
            self._alpr_worker_thread.join(timeout=3.0)
            logger.info("✅ Luồng ALPR đã đóng an toàn.")

# --- END OF FILE services/violation_service.py ---