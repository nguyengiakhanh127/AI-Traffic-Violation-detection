# --- START OF FILE services/detection_service.py ---

import logging
import numpy as np
from typing import List, Optional
import supervision as sv # [THÊM MỚI]: Bắt buộc để typing chuẩn

from core.vehicle import Vehicle, VehicleManager
from infrastructure.ai_adapters.yaml_mapper import YAML_ClassMapper

logger = logging.getLogger("DetectionService")

class DetectionService:
    """
    Dịch vụ cầu nối giữa đầu ra của AI (Supervision/YOLO + ByteTrack) 
    và Hệ thống Quản lý Phương tiện (VehicleManager).
    """
    
    def __init__(self, class_mapper: YAML_ClassMapper, vehicle_manager: VehicleManager):
        self.class_mapper = class_mapper
        self.vehicle_manager = vehicle_manager

    def process_frame(self, frame: np.ndarray, detections: Optional[sv.Detections]) -> List[Vehicle]:
        """
        :param detections: Đối tượng Detections chuẩn của SuperVision
        """
        if frame is None or detections is None or len(detections) == 0:
            # Vẫn gọi load_from_detections để VehicleManager dọn dẹp xe bị mất dấu (Lost Tracks)
            return self.vehicle_manager.load_from_detections([], frame.shape[:2], frame)

        h_img, w_img = frame.shape[:2]
        formatted_detections = []

        # Kiểm tra tracker_id an toàn theo chuẩn SuperVision
        if detections.tracker_id is not None:
            for track_id, class_id, bbox in zip(detections.tracker_id, detections.class_id, detections.xyxy):
                vehicle_type = self.class_mapper.get_vehicle_type(class_id)
                x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                formatted_detections.append((int(track_id), vehicle_type, x1, y1, x2, y2))

        # Lưu ý: Do module Core được giữ nguyên, vẫn phải truyền raw_frame 
        # để VehicleManager thực hiện nén ảnh. (Cần cải thiện Core trong tương lai).
        current_vehicles = self.vehicle_manager.load_from_detections(
            detections=formatted_detections, 
            frame_shape=(h_img, w_img),
            raw_frame=frame
        )

        return current_vehicles

# --- END OF FILE services/detection_service.py ---