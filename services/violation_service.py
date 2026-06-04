import os
import logging
import numpy as np
import cv2
from datetime import datetime
from typing import List

# [THÊM MỚI 1]: Import thư viện quản lý Thread Pool
from concurrent.futures import ThreadPoolExecutor

from core.vehicle import Vehicle
from core.engine import ViolationEvent, InspectionContext 
from core.trafficlight import TrafficLight
from infrastructure.evidence_generator import EvidenceGenerator

# [THÊM MỚI 2]: Import ALPR Service
from infrastructure.ai_adapters.alpr.plate_recognizer import LicensePlateRecognizer

logger = logging.getLogger("ViolationService")

class ViolationService:
    def __init__(self, rule_engine, record_manager, video_buffer, lane_manager, zone_manager, db_service=None, alpr_service=None):
        self.rule_engine = rule_engine
        self.record_manager = record_manager
        self.video_buffer = video_buffer
        self.lane_manager = lane_manager
        self.zone_manager = zone_manager
        self.db_service = db_service 
        self.enable_db_logging = False 
        
        self.current_camera_id = None 

        # [THÊM MỚI 3]: Nhận ALPR service và tạo ThreadPool (max 2 luồng để không ăn hết CPU)
        self.alpr_service: LicensePlateRecognizer = alpr_service
        self.background_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="OCR_Worker")

    def inspect_and_log(
        self, active_vehicles: List[Vehicle], current_time: datetime, frame: np.ndarray, 
        traffic_lights: List['TrafficLight'] = None
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
                        
                        # (Có thể mở lại if self.enable_db_logging nếu muốn điều khiển qua GUI)
                        self._trigger_evidence_chain(vehicle, event, new_record, current_time, current_lane, evidence_dir)
                            
        return new_violations_this_frame

    def _trigger_evidence_chain(self, vehicle, event, record, current_time, current_lane, event_folder: str) -> None:
        try:
            # 1. Ghi vào CSDL TRƯỚC để lấy ID (OCR cần ID này để update ngược lại)
            insert_id = None
            if self.db_service and self.current_camera_id:
                lane_str = current_lane.lane_id if current_lane else "Ngoài làn"
                
                insert_id = self.db_service.violations.insert(
                    camera_id=self.current_camera_id,
                    thoi_gian=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    ma_loi=event.error_name,
                    loai_xe=vehicle.vehicle_type.name,
                    lan_duong=lane_str,
                    bien_so="", 
                    duong_dan=event_folder
                )
                if insert_id > 0:
                    logger.info(f"💾 Đã lưu DB (ID: {insert_id}).")
                else:
                    logger.error("❌ Lưu Database thất bại!")
            else:
                logger.warning("⚠️ Bỏ qua lưu DB vì chưa cấu hình Camera ID.")

            file_timestamp = current_time.strftime("%Hh%Mm%Ss_%f")[:-3]

            # 2. Kích hoạt xuất Video
            video_filepath = os.path.join(event_folder, f"{file_timestamp}_video.mp4")
            self.video_buffer.trigger_export(video_filepath)

            # 3. Kích hoạt xuất Ảnh
            EvidenceGenerator.export_evidence_images(
                vehicle=vehicle, 
                violation_code=event.error_name,
                img_dir=event_folder, 
                timestamp_str=file_timestamp
            )

            if self.alpr_service and insert_id is not None:
                # Trích xuất ma trận ảnh xe ngay tại đây
                vehicle_crop = EvidenceGenerator.extract_crop_for_ocr(vehicle, event.error_name)
                
                if vehicle_crop is not None:
                    # [VÁ LỖI TẠI ĐÂY]: Kiểm tra xem ThreadPool có còn sống không.
                    # Nếu nó bằng None hoặc đã bị shutdown (cờ _shutdown = True) -> Tạo cái mới!
                    if getattr(self, 'background_executor', None) is None or self.background_executor._shutdown:
                        logger.info("Khởi tạo lại ThreadPool cho OCR...")
                        from concurrent.futures import ThreadPoolExecutor # Đảm bảo đã import
                        self.background_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="OCR_Worker")
                    
                    # Ném task vào ThreadPool
                    self.background_executor.submit(
                        self._run_ocr_task, insert_id, vehicle_crop, event_folder, file_timestamp
                    )

        except Exception as e:
            logger.error(f"❌ Lỗi khi thực thi chuỗi sinh bằng chứng: {e}")

    # ==============================================================
    # [THÊM MỚI]: HÀM CHẠY NGẦM BỞI THREAD POOL ĐỂ ĐỌC BIỂN SỐ
    # ==============================================================
    def _run_ocr_task(self, record_id: int, vehicle_crop: np.ndarray, event_folder: str, timestamp_str: str):
        try:
            # 1. Gọi AI nhận diện (Sẽ nhận về 2 biến)
            plate_text, plate_img = self.alpr_service.recognize(vehicle_crop)
            
            # 2. Lưu ảnh biển số ra đĩa (Nếu có)
            if plate_img is not None and event_folder:
                plate_filepath = os.path.join(event_folder, f"{timestamp_str}_5_plate_crop.jpg")
                cv2.imwrite(plate_filepath, plate_img)
            
            # 3. Cập nhật lại CSDL
            if self.db_service:
                self.db_service.violations.update_license_plate(record_id, plate_text)
                
                if plate_text != "Không xác định":
                    logger.info(f"🔎 [OCR THÀNH CÔNG]: ID {record_id} -> Biển số: {plate_text} (Đã lưu ảnh)")
                else:
                    logger.info(f"🔎 [OCR THẤT BẠI]: ID {record_id} không nhận diện được chữ.")
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi chạy luồng nền OCR: {e}")
            if self.db_service:
                try: self.db_service.violations.update_license_plate(record_id, "Không xác định")
                except: pass
        
    def shutdown(self):
        """Hàm dọn dẹp khi tắt phần mềm hoặc reset hệ thống"""
        if hasattr(self, 'background_executor'):
            logger.info("Đang chờ OCR xử lý nốt các biển số cuối cùng...")
            self.background_executor.shutdown(wait=True)
            logger.info("Luồng OCR đã đóng an toàn.")