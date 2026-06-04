import logging
import numpy as np
from typing import List, Any

from core.vehicle import Vehicle, VehicleManager
from infrastructure.ai_adapters.yaml_mapper import YAML_ClassMapper

logger = logging.getLogger("DetectionService")

class DetectionService:
    """
    Service chịu trách nhiệm cầu nối giữa đầu ra của AI (YOLO + Tracker) 
    và Hệ thống Quản lý Phương tiện (VehicleManager) của tầng Core.
    """
    
    def __init__(self, class_mapper: YAML_ClassMapper, vehicle_manager: VehicleManager):
        self.class_mapper = class_mapper
        self.vehicle_manager = vehicle_manager

    def process_frame(self, frame: np.ndarray, detections: Any) -> List[Vehicle]:
        if frame is None or detections is None:
            return []

        h_img, w_img = frame.shape[:2]
        formatted_detections = []

        if hasattr(detections, 'tracker_id') and detections.tracker_id is not None:
            for track_id, class_id, bbox in zip(detections.tracker_id, detections.class_id, detections.xyxy):
                vehicle_type = self.class_mapper.get_vehicle_type(class_id)
                x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]) # Ép kiểu an toàn
                formatted_detections.append((int(track_id), vehicle_type, x1, y1, x2, y2))

        # [CẬP NHẬT TRỌNG TÂM]: Phải truyền thêm raw_frame=frame vào để Vehicle nén ảnh JPEG!
        current_vehicles = self.vehicle_manager.load_from_detections(
            detections=formatted_detections, 
            frame_shape=(h_img, w_img),
            raw_frame=frame
        )

        return current_vehicles
