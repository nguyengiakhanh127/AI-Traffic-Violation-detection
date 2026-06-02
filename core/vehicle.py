from typing import Optional, Deque, Dict, List, Tuple
from collections import deque
import numpy as np
from utils.enums import TrafficVehicleType
from geometry.primitives import Vertex, Vector2D
from geometry.shapes import Edge
import math
class VehicleCoordinate:
    def __init__(
        self, 
        initial_centroid: Vertex,
        initial_routing_point: Vertex,      
        initial_footprint_left: Vertex,
        initial_footprint_right: Vertex,
        window_size: int = 5,
       
    ):
        self.current_position: Vertex = initial_centroid
        self.previous_position: Optional[Vertex] = None

        self.direction: Vector2D = Vector2D(0.0, 0.0) 
        
        self.window_size = window_size
        self.position_history: Deque[Vertex] = deque(maxlen=self.window_size)
        self.position_history.append(initial_centroid)

        self.routing_point: Vertex = initial_routing_point
        self.previous_routing_point: Optional[Vertex] = None

        self.footprint_left: Vertex = initial_footprint_left
        self.previous_footprint_left: Optional[Vertex] = None

        self.footprint_right: Vertex = initial_footprint_right
        self.previous_footprint_right: Optional[Vertex] = None

        self.stationary_frames: int = 0

        self.full_trajectory: List[Vertex] = []
        self.age: int = 1 

    def update_position(
        self, 
        new_centroid: Vertex, 
        new_routing_point: Vertex, 
        new_footprint_left: Vertex,
        new_footprint_right: Vertex
    ) -> None:
        self.previous_position = self.current_position
        self.current_position = new_centroid
        self.position_history.append(new_centroid)

        self.previous_routing_point = self.routing_point
        self.routing_point = new_routing_point

        self.previous_footprint_left = self.footprint_left
        self.footprint_left = new_footprint_left

        self.previous_footprint_right = self.footprint_right
        self.footprint_right = new_footprint_right

        self.age += 1

        if self.age % 2 == 0:
            self.full_trajectory.append(self.current_position)

        if not self.is_moving(movement_threshold=1.0):
            self.stationary_frames += 1
        else:
            self.stationary_frames = max(0, self.stationary_frames - 2)

        if len(self.position_history) > 1:
            oldest_pos = self.position_history[0]
            dx = self.current_position.x - oldest_pos.x
            dy = self.current_position.y - oldest_pos.y
            frames_passed = len(self.position_history) - 1
            self.direction = Vector2D(dx / frames_passed, dy / frames_passed)
        else:
            self.direction = Vector2D(0.0, 0.0)

    def is_moving(self, movement_threshold: float = 1.0) -> bool:
        if len(self.position_history) < self.window_size:
            return False

        avg_speed = math.hypot(self.direction.dx, self.direction.dy)
        return avg_speed > movement_threshold
    
    @property
    def is_history_full(self) -> bool:
        return len(self.position_history) >= self.position_history.maxlen

class VehicleViolationState:
    def __init__(self):
        self.active_violations: set = set()

    def add(self, violation_type) -> None:
        self.active_violations.add(violation_type)

    def has(self, violation_type) -> bool:
        return violation_type in self.active_violations

    def clear(self) -> None:
        self.active_violations.clear()


class Vehicle:
    def __init__(
        self, 
        track_id: int, 
        vehicle_type: TrafficVehicleType, 
        initial_centroid: Vertex,
        initial_routing_point: Vertex,
        initial_footprint_left: Vertex,
        initial_footprint_right: Vertex,
        window_size: int = 5
    ):
        self.id: int = track_id
        self.vehicle_type: TrafficVehicleType = vehicle_type
        
        self.coordinate = VehicleCoordinate(
            initial_centroid, 
            initial_routing_point, 
            initial_footprint_left, 
            initial_footprint_right, 
            window_size
        )
        self.current_bbox = (0,0,0,0)
        self.is_stable: bool = False
        self.violation_state = VehicleViolationState()

        self.first_frame: Optional[np.ndarray] = None
        self.first_bbox: Optional[Tuple[int, int, int, int]] = None
        
        self.violation_frames: Dict[str, np.ndarray] = {}
        self.violation_bboxes: Dict[str, Tuple[int, int, int, int]] = {}

    @property
    def current_position(self) -> Vertex: return self.coordinate.current_position

    @property
    def previous_position(self) -> Optional[Vertex]: return self.coordinate.previous_position

    @property
    def direction(self) -> Vector2D: return self.coordinate.direction

    @property
    def position_history(self) -> Deque[Vertex]: return self.coordinate.position_history

    @property
    def routing_point(self) -> Vertex: return self.coordinate.routing_point

    @property
    def previous_routing_point(self) -> Optional[Vertex]: return self.coordinate.previous_routing_point

    @property
    def footprint_left(self) -> Vertex: return self.coordinate.footprint_left

    @property
    def previous_footprint_left(self) -> Optional[Vertex]: return self.coordinate.previous_footprint_left

    @property
    def footprint_right(self) -> Vertex: return self.coordinate.footprint_right

    @property
    def previous_footprint_right(self) -> Optional[Vertex]: return self.coordinate.previous_footprint_right

    @property
    def stationary_frames(self) -> int: return self.coordinate.stationary_frames

    @property
    def active_violations(self) -> set: return self.violation_state.active_violations
    
    def update_position(self, new_centroid: Vertex, new_routing_point: Vertex, new_footprint_left: Vertex, new_footprint_right: Vertex) -> None:
        self.coordinate.update_position(new_centroid, new_routing_point, new_footprint_left, new_footprint_right)

    def is_moving(self, movement_threshold: float = 1.0) -> bool:
        return self.coordinate.is_moving(movement_threshold)


class VehicleManager:
    """
        Lớp này phụ trách quản lý vòng đời phương tiện
    """

    # Cấu hình sẵn các tham số tương ứng với tọa độ bánh xe cho phương tiện
    ANCHOR_CONFIG = {
        TrafficVehicleType.CAR:         {'y_drop_ratio': 0.90, 'x_shrink_ratio': 0.15},
        TrafficVehicleType.TRUCK:       {'y_drop_ratio': 0.95, 'x_shrink_ratio': 0.25},
        TrafficVehicleType.BUS:         {'y_drop_ratio': 0.95, 'x_shrink_ratio': 0.25},
        TrafficVehicleType.CONTAINER:   {'y_drop_ratio': 0.95, 'x_shrink_ratio': 0.10},
        TrafficVehicleType.MOTORCYCLE:  {'y_drop_ratio': 0.90, 'x_shrink_ratio': 0.0},
        TrafficVehicleType.BICYCLE:     {'y_drop_ratio': 0.98, 'x_shrink_ratio': 0.0},
        TrafficVehicleType.UNKNOWN:     {'y_drop_ratio': 0.90, 'x_shrink_ratio': 0.10},
    }
    def __init__(self, value: int = 10):
        # Định nghĩa tham số xác định rằng một phương tiện được cho là rời khỏi khu vực
        self.max_frame_lost = value

        # Danh sách dictionary[id, Vehicle] lưu các phương tiện chưa rời khỏi khung hình hoặc mất dấu
        self._active_vehicles: Dict[int, Vehicle] = {}
        self._lost_tracks: Dict[int, int] = {}
        self._vehicle_sizes: Dict[int, Tuple[float, float]] = {}

    @staticmethod
    def _to_scalar(val) -> float:
        try:
            return float(np.asarray(val).flatten()[0])
        except Exception:
            return float(val)

    # Làm mịn kết quả bounding box với bộ lọc nhiễu EMA
    def _smooth_bbox_size(self, vehicle_id: int, raw_w: float, raw_h: float) -> Tuple[float, float]:
        if self.is_new_vehicle(vehicle_id):
            self._vehicle_sizes[vehicle_id] = (raw_w, raw_h)
            return raw_w, raw_h

        old_w, old_h = self._vehicle_sizes[vehicle_id]

        #Không cho phép bbox vượt quá 15% chỉ trong 1 khung hình
        target_w = min(raw_w, old_w * 1.15)
        target_h = min(raw_h, old_h * 1.15)

        # Bộ lọc EMA với tham số alpha = 0.5
        alpha = 0.5
        smooth_w = alpha * raw_w + (1.0 - alpha) * old_w
        smooth_h = alpha * raw_h + (1.0 - alpha) * old_h

        self._vehicle_sizes[vehicle_id] = (smooth_w, smooth_h)
        return smooth_w, smooth_h
    
    @staticmethod
    def calculate_anchors(
        x1: float, y1: float, x2: float, y2: float, vehicle_type: TrafficVehicleType
    ) -> Tuple[Vertex, Vertex, Vertex, Vertex]:
        width = x2 - x1
        height = y2 - y1
        center_x = x1 + width / 2.0
        
        # Tâm xe
        centroid = Vertex(center_x, y1 + height / 2.0)
        
        # Tính tọa độ đã được "dời"
        config = VehicleManager.ANCHOR_CONFIG.get(vehicle_type, VehicleManager.ANCHOR_CONFIG[TrafficVehicleType.UNKNOWN])
        
        road_contact_y = y1 + (height * config['y_drop_ratio'])
        
        # Tọa độ gần với footprint có "dời" một khoảng y
        routing_point = Vertex(center_x, road_contact_y)

        # Kiểm tra loại  xe
        if vehicle_type in [
            TrafficVehicleType.CAR,
            TrafficVehicleType.BUS,
            TrafficVehicleType.CONTAINER,
            TrafficVehicleType.TRUCK
        ]:
            # Định nghĩa bánh xe trái và bánh xe phải
            shrink_amount = width * config['x_shrink_ratio']
            footprint_left = Vertex(x1 + shrink_amount, road_contact_y)
            footprint_right = Vertex(x2 - shrink_amount, road_contact_y)
        else:
            # Định nghĩa bánh xe trái và phải bằng bánh xe dưới ~ routing_point
            footprint_left = Vertex(center_x, road_contact_y)
            footprint_right = Vertex(center_x, road_contact_y)
        return centroid, routing_point, footprint_left, footprint_right

    def load_from_detections(
        self, detections: List[Tuple[int, TrafficVehicleType, float, float, float, float]],
        frame_shape: Tuple[int, int]
    ) -> List[Vehicle]:
        
        seen_this_frame = set()
        
        # Bóc tách kích thước ảnh an toàn
        h_img, w_img = int(self._to_scalar(frame_shape[0])), int(self._to_scalar(frame_shape[1]))
        margin = 5

        for track_id, vehicle_type, x1, y1, x2, y2 in detections:
            # 1. Chuẩn hóa dữ liệu đầu vào
            v_id = int(self._to_scalar(track_id))
            seen_this_frame.add(v_id)

            _x1, _y1 = self._to_scalar(x1), self._to_scalar(y1)
            _x2, _y2 = self._to_scalar(x2), self._to_scalar(y2)

            raw_w, raw_h = _x2 - _x1, _y2 - _y1
            center_x, top_y = (_x1 + _x2) / 2.0, _y1

            # 2. Bộ lọc kháng nhiễu Bbox
            smooth_w, smooth_h = self._smooth_bbox_size(v_id, raw_w, raw_h)

            # 3. Tái tạo Bbox an toàn
            safe_x1, safe_y1 = center_x - smooth_w / 2.0, top_y
            safe_x2, safe_y2 = center_x + smooth_w / 2.0, top_y + smooth_h

            # 4. Sinh điểm neo định tuyến
            centroid, r_point, foot_l, foot_r = self.calculate_anchors(
                safe_x1, safe_y1, safe_x2, safe_y2, vehicle_type
            )

            # 5. Cập nhật vòng đời phương tiện
            if self.is_new_vehicle(v_id):
                self.add_vehicle(v_id, vehicle_type, centroid, r_point, foot_l, foot_r)
            else:
                self.update_vehicle(v_id, centroid, r_point, foot_l, foot_r)

            # 6. Ghi nhận siêu dữ liệu cho Bằng chứng (Metadata)
            vehicle = self._active_vehicles[v_id]
            vehicle.current_bbox = (int(safe_x1), int(safe_y1), int(safe_x2), int(safe_y2))

            is_touching_border = (
                safe_x1 <= margin or safe_y1 <= margin or 
                safe_x2 >= (w_img - margin) or safe_y2 >= (h_img - margin)
            )
            vehicle.is_stable = (vehicle.coordinate.age >= 5) and (is_touching_border)

        # 7. Dọn dẹp các phương tiện mất dấu
        self._cleanup_lost_tracks(seen_this_frame)

        return [self._active_vehicles[t_id] for t_id in seen_this_frame]
    
    def _cleanup_lost_tracks(self, seen_this_frame: set) -> None:
        active_track_ids = list(self._active_vehicles.keys()) 
        for v_id in active_track_ids:
            if v_id not in seen_this_frame:
                self._lost_tracks[v_id] += 1
                if self._lost_tracks[v_id] > self.max_frame_lost:
                    self.del_vehicle(v_id)   

    def is_new_vehicle(self, vehicle_id: int) -> bool:
        return int(vehicle_id) not in self._active_vehicles
    
    def add_vehicle(self, vehicle_id: int, vehicle_type: TrafficVehicleType, current_centroid: Vertex, current_routing_point: Vertex, current_left: Vertex, current_right: Vertex) -> None:
        v_id = int(vehicle_id)
        new_vehicle = Vehicle(
            track_id=v_id, vehicle_type=vehicle_type, 
            initial_centroid=current_centroid,
            initial_routing_point=current_routing_point,
            initial_footprint_left=current_left,
            initial_footprint_right=current_right
        )
        self._active_vehicles[v_id] = new_vehicle
        self._lost_tracks[v_id] = 0

    def update_vehicle(self, vehicle_id: int, current_centroid: Vertex, current_routing_point: Vertex, current_left: Vertex, current_right: Vertex) -> None:
        v_id = int(vehicle_id)
        self._active_vehicles[v_id].update_position(current_centroid, current_routing_point, current_left, current_right)
        self._lost_tracks[v_id] = 0

    def del_vehicle(self, vehicle_id: int) -> None:
        v_id = int(vehicle_id)
        self._active_vehicles[v_id].violation_state.clear()
        del self._active_vehicles[v_id]
        del self._lost_tracks[v_id]
        # [CẬP NHẬT: Dọn dẹp bộ nhớ sizes]
        if v_id in self._vehicle_sizes:
            del self._vehicle_sizes[v_id]

    def get_all_active_vehicles(self) -> List[Vehicle]:
        return list(self._active_vehicles.values())

    def get_vehicle(self, track_id: int) -> Optional[Vehicle]:
        return self._active_vehicles.get(track_id)