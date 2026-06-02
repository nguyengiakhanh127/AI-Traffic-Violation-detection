import os
import logging
import numpy as np
from datetime import datetime
from typing import List, Optional

from core.vehicle import Vehicle
from core.lane import LaneManager, ZoneManager
# from core.traffic_light import TrafficLight # Bỏ comment khi làm xong TrafficLight
from core.engine import ViolationRuleEngine, ViolationEvent
from core.records import ViolationRecordManager
from infrastructure.evidence_writer import VideoRingBuffer
from infrastructure.evidence_generator import EvidenceGenerator

logger = logging.getLogger("ViolationService")

class ViolationService:
    def __init__(self, rule_engine, record_manager, video_buffer, lane_manager, zone_manager, db_service=None):
        self.rule_engine = rule_engine
        self.record_manager = record_manager
        self.video_buffer = video_buffer
        self.lane_manager = lane_manager
        self.zone_manager = zone_manager
        self.db_service = db_service # Lưu tham chiếu DB
        self.enable_db_logging = False 
        
        self.current_camera_id = None # [THÊM MỚI]: Để biết đang quét AI cho Camera nào

    def inspect_and_log(
        self, active_vehicles: List[Vehicle], current_time: datetime, frame: np.ndarray
    ) -> List[ViolationEvent]:
        new_violations_this_frame = []

        for vehicle in active_vehicles:
            if not vehicle.is_stable:
                continue
                
            current_lane = None
            current_lane = self.lane_manager.get_lane_at_position(vehicle.routing_point)
                
            matched_zones = self.zone_manager.get_zones_at_position(vehicle.routing_point)

            # 1. Gọi Động cơ Luật
            violations = self.rule_engine.inspect_vehicle(
                vehicle=vehicle, 
                lane=current_lane, 
                zones=matched_zones, 
                current_time=current_time
            )
            
            # 2. Xử lý Vi phạm
            if violations:
                for event in violations:
                    print(event)
                    new_record = self.record_manager.log_violation(vehicle, event, current_time)
                    
                    if new_record:
                        logger.info(f"🚨 [PHÁT HIỆN]: {event.error_name} - Xe {vehicle.vehicle_type.name} ID:{vehicle.id}")
                        new_violations_this_frame.append(event)
                        
                        # [THÊM MỚI]: Chụp ảnh bằng chứng lúc vi phạm (Last Seen) lưu vào xe
                        vehicle.violation_frames[event.error_name] = frame # BẮT BUỘC PHẢI LÀ frame.copy()
                        vehicle.violation_bboxes[event.error_name] = vehicle.current_bbox
                        
                        # Kích hoạt chuỗi hành động sinh bằng chứng
                        if self.enable_db_logging:
                            self._trigger_evidence_chain(vehicle, event, new_record, current_time, current_lane)
                            

        return new_violations_this_frame

    def _trigger_evidence_chain(self, vehicle, event, record, current_time, current_lane) -> None:
        """
        [Hàm Private]: Thực thi chuỗi lưu ảnh, video và xuất file JSON biên bản.
        """
        try:
            # 1. Chụp ảnh tại khoảnh khắc bị bắt lỗi (Last Seen)
            import numpy as np
            # Giả định frame gốc có thể được lưu ở một biến toàn cục hoặc truyền qua,
            # Tuy nhiên, ta đã yêu cầu VehicleManager gán last_frame bên trong. 
            # Đảm bảo logic VehicleManager đã gán last_frame trước khi chốt lỗi.
            # Lưu ý: Cần điều chỉnh nếu kiến trúc truyền frame bị thay đổi.
            
            # 2. Yêu cầu RecordManager cung cấp đường dẫn thư mục chuẩn
            event_folder = self.record_manager.get_evidence_directory(
                violation_code=event.error_name,
                vehicle_type_name=vehicle.vehicle_type.name,
                current_time=current_time
            )
            
            # Chuỗi thời gian chuẩn hóa để đặt tên file
            file_timestamp = current_time.strftime("%Hh%Mm%Ss_%f")[:-3]
            
            # 3. Kích hoạt xuất Video (Thread chạy nền)
            video_filepath = os.path.join(event_folder, f"{file_timestamp}_video.mp4")
            self.video_buffer.trigger_export(video_filepath)
            
            # 4. Kích hoạt xuất 4 Hình ảnh Bằng chứng
            EvidenceGenerator.export_evidence_images(
                vehicle=vehicle, 
                violation_code=event.error_name,
                img_dir=event_folder, 
                timestamp_str=file_timestamp
            )

            lane_str = current_lane.lane_id if current_lane is not None else "Ngoài làn"
            
            if self.db_service and self.current_camera_id:
                db_data = {
                    "camera_id": self.current_camera_id,
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "violation_code": event.error_name,
                    "vehicle_type": vehicle.vehicle_type.name,
                    "lane_id": lane_str,  # <--- HẾT "TODO", DÙNG ID LÀN THỰC TẾ
                    "license_plate": record.license_plate,
                    "evidence_path": event_folder
                }
                
                insert_id = self.db_service.insert_violation(db_data)
                
                if insert_id > 0:
                    logger.info(f"💾 Đã lưu dữ liệu vi phạm vào Database (Record ID: {insert_id}).")
                else:
                    logger.error("❌ Lưu Database thất bại!")
            else:
                logger.warning("⚠️ Bỏ qua lưu DB vì db_service hoặc camera_id chưa được cấu hình.")
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi thực thi chuỗi sinh bằng chứng: {e}")

# --- END OF FILE services/violation_service.py ---