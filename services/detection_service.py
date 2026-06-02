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
        """
        Bóc tách dữ liệu AI, ánh xạ nhãn, và cập nhật vòng đời phương tiện.
        Trả về danh sách các đối tượng Vehicle đang active trong khung hình hiện tại.
        
        - detections: Đối tượng kết quả trả về từ bộ Tracker thuộc thư viện SuperVision
        """
        if frame is None or detections is None:
            return []

        h_img, w_img = frame.shape[:2]
        formatted_detections = []

        # Rào chắn an toàn: Đảm bảo có đối tượng được track trong frame này
        if hasattr(detections, 'tracker_id') and detections.tracker_id is not None:
            
            # Lặp qua các kết quả
            for track_id, class_id, bbox in zip(detections.tracker_id, detections.class_id, detections.xyxy):
                
                # 1. Ánh xạ AI Label -> Enum hệ thống (TrafficVehicleType)
                vehicle_type = self.class_mapper.get_vehicle_type(class_id)
                
                # 2. Rút trích tọa độ
                x1, y1, x2, y2 = bbox
                
                formatted_detections.append((
                    track_id, 
                    vehicle_type, 
                    x1, y1, x2, y2
                ))

        # Truyền dữ liệu qua cho lớp "Vehicle Manager" nhằm quản lý/ lọc dữ liệu/ khởi tạo dữ liệu
        current_vehicles = self.vehicle_manager.load_from_detections(
            formatted_detections, 
            frame_shape=(h_img, w_img)
        )

        # Trả về danh sách các phương tiện xuất hiện trong frame
        return current_vehicles
