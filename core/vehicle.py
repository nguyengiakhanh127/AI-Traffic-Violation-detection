import cv2
import math
import numpy as np
from typing import Optional, Deque, Dict, List, Tuple
from collections import deque
from dataclasses import dataclass

from utils.enums import TrafficVehicleType
from geometry.primitives import Vertex, Vector2D


# ==========================================
# 1. MODELS (Lưu trữ trạng thái phương tiện)
# ==========================================

@dataclass
class VehicleAnchors:
    """Đóng gói toàn bộ tọa độ không gian của xe trong một khung hình"""
    centroid: Vertex
    routing_point: Vertex
    # Dùng Optional vì xe 2 bánh không có vệt bánh xe trái/phải
    left_wheel: Optional[Vertex] = None
    right_wheel: Optional[Vertex] = None


class VehicleCoordinate:
    """Quản lý động học và lịch sử di chuyển của xe"""
    def __init__(self, initial_anchors: VehicleAnchors, window_size: int = 5, max_trajectory: int = 90):
        self.current_anchors: VehicleAnchors = initial_anchors
        self.previous_anchors: Optional[VehicleAnchors] = None

        # 1 Queue duy nhất cho cả tính toán động học và vẽ UI (Trail)
        self.trajectory: Deque[Vertex] = deque(maxlen=max_trajectory)
        self.trajectory.append(initial_anchors.routing_point)
        
        self.window_size = window_size
        self.direction: Vector2D = Vector2D(0.0, 0.0) 
        self.stationary_frames: int = 0
        self.age: int = 1 

    def update(self, new_anchors: VehicleAnchors) -> None:
        self.previous_anchors = self.current_anchors
        self.current_anchors = new_anchors
        self.age += 1

        self.trajectory.append(new_anchors.routing_point)
        self._update_kinematics()

    def _update_kinematics(self) -> None:
        history_len = len(self.trajectory)
        if history_len >= 2:
            compare_idx = max(0, history_len - self.window_size)
            past_point = self.trajectory[compare_idx]
            current_point = self.trajectory[-1]

            frames_passed = max(1, history_len - compare_idx - 1)
            self.direction = Vector2D(
                (current_point.x - past_point.x) / frames_passed, 
                (current_point.y - past_point.y) / frames_passed
            )
        else:
            self.direction = Vector2D(0.0, 0.0)

        if not self.is_moving(movement_threshold=1.0):
            self.stationary_frames += 1
        else:
            self.stationary_frames = max(0, self.stationary_frames - 2)

    def is_moving(self, movement_threshold: float = 1.0) -> bool:
        if len(self.trajectory) < self.window_size:
            return False
        return math.hypot(self.direction.dx, self.direction.dy) > movement_threshold


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
    """Thực thể Phương tiện (Tối ưu RAM bằng In-Memory Compression)"""
    def __init__(self, track_id: int, vehicle_type: TrafficVehicleType, anchors: VehicleAnchors, window_size: int = 5):
        self.id: int = track_id
        self.vehicle_type: TrafficVehicleType = vehicle_type
        self.coordinate = VehicleCoordinate(anchors, window_size)
        
        self.current_bbox = (0,0,0,0)
        self.is_stable: bool = False
        self.violation_state = VehicleViolationState()

        # Nén ảnh dạng bytes
        self._first_frame_bytes: Optional[bytes] = None
        self._violation_frames_bytes: Dict[str, bytes] = {}
        self.first_bbox: Optional[Tuple[int, int, int, int]] = None
        self.violation_bboxes: Dict[str, Tuple[int, int, int, int]] = {}

    def set_first_frame(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> None:
        success, encoded_image = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        if success:
            self._first_frame_bytes = encoded_image.tobytes()
            self.first_bbox = bbox


    def get_first_frame(self) -> Optional[np.ndarray]:
        if not self._first_frame_bytes: return None
        return cv2.imdecode(np.frombuffer(self._first_frame_bytes, np.uint8), cv2.IMREAD_COLOR)

    def add_violation_frame(self, violation_code: str, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> None:
        success, encoded_image = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 60])
        if success:
            self._violation_frames_bytes[violation_code] = encoded_image.tobytes()
            self.violation_bboxes[violation_code] = bbox

    def get_violation_frame(self, violation_code: str) -> Optional[np.ndarray]:
        byte_data = self._violation_frames_bytes.get(violation_code)
        if not byte_data: return None
        return cv2.imdecode(np.frombuffer(byte_data, np.uint8), cv2.IMREAD_COLOR)

    # --- Properties (Delegation) ---
    @property
    def current_position(self) -> Vertex: return self.coordinate.current_anchors.centroid
    @property
    def previous_position(self) -> Optional[Vertex]: 
        return self.coordinate.previous_anchors.centroid if self.coordinate.previous_anchors else None
    
    @property
    def routing_point(self) -> Vertex: return self.coordinate.current_anchors.routing_point
    @property
    def previous_routing_point(self) -> Optional[Vertex]: 
        return self.coordinate.previous_anchors.routing_point if self.coordinate.previous_anchors else None

    @property
    def footprint_left(self) -> Optional[Vertex]: return self.coordinate.current_anchors.left_wheel
    @property
    def previous_footprint_left(self) -> Optional[Vertex]: 
        return self.coordinate.previous_anchors.left_wheel if self.coordinate.previous_anchors else None

    @property
    def footprint_right(self) -> Optional[Vertex]: return self.coordinate.current_anchors.right_wheel
    @property
    def previous_footprint_right(self) -> Optional[Vertex]: 
        return self.coordinate.previous_anchors.right_wheel if self.coordinate.previous_anchors else None

    @property
    def direction(self) -> Vector2D: return self.coordinate.direction
    @property
    def stationary_frames(self) -> int: return self.coordinate.stationary_frames
    @property
    def active_violations(self) -> set: return self.violation_state.active_violations

    def is_moving(self, threshold: float = 2.0) -> bool: return self.coordinate.is_moving(threshold)


# ==========================================
# 2. UTILITY CLASSES
# ==========================================

class BBoxSmoother:
    def __init__(self, alpha: float = 0.8, max_growth_ratio: float = 1.15):
        self.alpha = alpha
        self.max_growth_ratio = max_growth_ratio
        self._vehicle_sizes: Dict[int, Tuple[float, float]] = {}

    def smooth(self, vehicle_id: int, raw_w: float, raw_h: float) -> Tuple[float, float]:
        if vehicle_id not in self._vehicle_sizes:
            self._vehicle_sizes[vehicle_id] = (raw_w, raw_h)
            return raw_w, raw_h

        old_w, old_h = self._vehicle_sizes[vehicle_id]
        target_w = min(raw_w, old_w * self.max_growth_ratio)
        target_h = min(raw_h, old_h * self.max_growth_ratio)

        smooth_w = self.alpha * target_w + (1.0 - self.alpha) * old_w
        smooth_h = self.alpha * target_h + (1.0 - self.alpha) * old_h

        self._vehicle_sizes[vehicle_id] = (smooth_w, smooth_h)
        return smooth_w, smooth_h

    def clear(self, vehicle_id: int) -> None:
        if vehicle_id in self._vehicle_sizes:
            del self._vehicle_sizes[vehicle_id]


class VehicleAnchorCalculator:
    DEFAULT_CONFIG = {
        TrafficVehicleType.CAR:         {'y_drop_ratio': 0.90, 'x_shrink_ratio': 0.15},
        TrafficVehicleType.TRUCK:       {'y_drop_ratio': 0.95, 'x_shrink_ratio': 0.25},
        TrafficVehicleType.BUS:         {'y_drop_ratio': 0.95, 'x_shrink_ratio': 0.25},
        TrafficVehicleType.CONTAINER:   {'y_drop_ratio': 0.95, 'x_shrink_ratio': 0.10},
        TrafficVehicleType.MOTORCYCLE:  {'y_drop_ratio': 0.90, 'x_shrink_ratio': 0.0},
        TrafficVehicleType.BICYCLE:     {'y_drop_ratio': 0.98, 'x_shrink_ratio': 0.0},
        TrafficVehicleType.UNKNOWN:     {'y_drop_ratio': 0.90, 'x_shrink_ratio': 0.10},
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self.DEFAULT_CONFIG

    def calculate(self, x1: float, y1: float, x2: float, y2: float, vehicle_type: TrafficVehicleType) -> VehicleAnchors:
        width, height = x2 - x1, y2 - y1
        center_x = x1 + width / 2.0
        centroid = Vertex(center_x, y1 + height / 2.0)
        
        cfg = self.config.get(vehicle_type, self.config[TrafficVehicleType.UNKNOWN])
        road_contact_y = y1 + (height * cfg['y_drop_ratio'])
        routing_point = Vertex(center_x, road_contact_y)

        if vehicle_type in [
            TrafficVehicleType.CAR, TrafficVehicleType.BUS, 
            TrafficVehicleType.CONTAINER, TrafficVehicleType.TRUCK
        ]:
            shrink_amount = width * cfg['x_shrink_ratio']
            left_wheel = Vertex(x1 + shrink_amount, road_contact_y)
            right_wheel = Vertex(x2 - shrink_amount, road_contact_y)
            return VehicleAnchors(centroid, routing_point, left_wheel, right_wheel)
        else:
            return VehicleAnchors(centroid, routing_point)


# ==========================================
# 3. MANAGER
# ==========================================

class VehicleManager:
    def __init__(self, max_frame_lost: int = 20):
        self.max_frame_lost = max_frame_lost
        self._active_vehicles: Dict[int, Vehicle] = {}
        self._lost_tracks: Dict[int, int] = {}
        
        self._smoother = BBoxSmoother()
        self._anchor_calculator = VehicleAnchorCalculator()

    def load_from_detections(
        self, detections: List[Tuple[int, TrafficVehicleType, float, float, float, float]],
        frame_shape: Tuple[int, int], raw_frame: np.ndarray
    ) -> List[Vehicle]:
        
        seen_this_frame = set()
        h_img, w_img = int(frame_shape[0]), int(frame_shape[1])
        margin = 5

        for track_id, vehicle_type, x1, y1, x2, y2 in detections:
            v_id = int(track_id)
            seen_this_frame.add(v_id)

            _x1, _y1, _x2, _y2 = float(x1), float(y1), float(x2), float(y2)
            raw_w, raw_h = _x2 - _x1, _y2 - _y1
            center_x, top_y = (_x1 + _x2) / 2.0, _y1

            smooth_w, smooth_h = self._smoother.smooth(v_id, raw_w, raw_h)
            safe_x1, safe_y1 = center_x - smooth_w / 2.0, top_y
            safe_x2, safe_y2 = center_x + smooth_w / 2.0, top_y + smooth_h
            current_bbox = (int(safe_x1), int(safe_y1), int(safe_x2), int(safe_y2))

            current_anchors = self._anchor_calculator.calculate(safe_x1, safe_y1, safe_x2, safe_y2, vehicle_type)

            if v_id not in self._active_vehicles:
                self._add_vehicle(v_id, vehicle_type, current_anchors)
                self._active_vehicles[v_id].set_first_frame(raw_frame, current_bbox)
            else:
                self._active_vehicles[v_id].coordinate.update(current_anchors)
                self._lost_tracks[v_id] = 0

            vehicle = self._active_vehicles[v_id]
            vehicle.current_bbox = current_bbox

            is_touching_border = (
                safe_x1 <= margin or safe_y1 <= margin or 
                safe_x2 >= (w_img - margin) or safe_y2 >= (h_img - margin)
            )
            vehicle.is_stable = (vehicle.coordinate.age >= 5) and (not is_touching_border)

        self._cleanup_lost_tracks(seen_this_frame)
        return [self._active_vehicles[t_id] for t_id in seen_this_frame]
    
    def _add_vehicle(self, v_id: int, v_type: TrafficVehicleType, anchors: VehicleAnchors) -> None:
        self._active_vehicles[v_id] = Vehicle(v_id, v_type, anchors)
        self._lost_tracks[v_id] = 0

    def _cleanup_lost_tracks(self, seen_this_frame: set) -> None:
        active_track_ids = list(self._active_vehicles.keys()) 
        for v_id in active_track_ids:
            if v_id not in seen_this_frame:
                self._lost_tracks[v_id] += 1
                if self._lost_tracks[v_id] > self.max_frame_lost:
                    self._del_vehicle(v_id)   

    def _del_vehicle(self, v_id: int) -> None:
        if v_id in self._active_vehicles:
            self._active_vehicles[v_id].violation_state.clear()
            del self._active_vehicles[v_id]
            del self._lost_tracks[v_id]
            self._smoother.clear(v_id)

    def get_all_active_vehicles(self) -> List[Vehicle]:
        return list(self._active_vehicles.values())

    def get_vehicle(self, track_id: int) -> Optional[Vehicle]:
        return self._active_vehicles.get(track_id)