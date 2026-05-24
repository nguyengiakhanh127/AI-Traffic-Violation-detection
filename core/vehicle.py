from typing import Optional, Deque, Dict, List, Tuple
from collections import deque
import numpy as np

from utils.enums import TrafficVehicleType
from geometry.primitives import Vertex, Vector2D
from geometry.shapes import Edge


class VehicleKinematics:
    def __init__(
        self, 
        initial_centroid: Vertex,
        initial_footprint_center: Vertex,
        initial_footprint_left: Vertex,
        initial_footprint_right: Vertex,
        window_size: int = 5
    ):
        self.current_position: Vertex = initial_centroid
        self.previous_position: Optional[Vertex] = None
        self.direction: Vector2D = Vector2D(0.0, 0.0) 
        
        self.window_size = window_size
        self.position_history: Deque[Vertex] = deque(maxlen=self.window_size)
        self.position_history.append(initial_centroid)

        self.footprint: Vertex = initial_footprint_center
        self.previous_footprint: Optional[Vertex] = None

        self.footprint_left: Vertex = initial_footprint_left
        self.previous_footprint_left: Optional[Vertex] = None

        self.footprint_right: Vertex = initial_footprint_right
        self.previous_footprint_right: Optional[Vertex] = None

        self.stationary_frames: int = 0

    def update_position(
        self, 
        new_centroid: Vertex, 
        new_footprint_center: Vertex,
        new_footprint_left: Vertex,
        new_footprint_right: Vertex
    ) -> None:
        self.previous_position = self.current_position
        self.current_position = new_centroid
        self.position_history.append(new_centroid)

        self.previous_footprint = self.footprint
        self.footprint = new_footprint_center

        self.previous_footprint_left = self.footprint_left
        self.footprint_left = new_footprint_left

        self.previous_footprint_right = self.footprint_right
        self.footprint_right = new_footprint_right

        if not self.is_moving(movement_threshold=1.0):
            self.stationary_frames += 1
        else:
            self.stationary_frames = 0  

        if len(self.position_history) > 1:
            oldest_pos = self.position_history[0]
            dx = self.current_position.x - oldest_pos.x
            dy = self.current_position.y - oldest_pos.y
            
            frames_passed = len(self.position_history) - 1
            self.direction = Vector2D(dx / frames_passed, dy / frames_passed)
        else:
            self.direction = Vector2D(0.0, 0.0)

    def is_moving(self, movement_threshold: float = 0.7) -> bool:
        if len(self.position_history) < self.window_size:
            return False
            
        avg_speed = np.linalg.norm(self.direction.as_array)
        return float(avg_speed) > movement_threshold


class ViolationState:
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
        initial_footprint_center: Vertex,
        initial_footprint_left: Vertex,
        initial_footprint_right: Vertex,
        window_size: int = 5
    ):
        self.track_id: int = track_id
        self.vehicle_type: TrafficVehicleType = vehicle_type
        
        self.kinematics = VehicleKinematics(
            initial_centroid, 
            initial_footprint_center, 
            initial_footprint_left, 
            initial_footprint_right, 
            window_size
        )
        self.violation_state = ViolationState()
        self.last_touched_edge: Optional[Edge] = None

    @property
    def current_position(self) -> Vertex:
        return self.kinematics.current_position

    @property
    def previous_position(self) -> Optional[Vertex]:
        return self.kinematics.previous_position

    @property
    def direction(self) -> Vector2D:
        return self.kinematics.direction

    @property
    def position_history(self) -> Deque[Vertex]:
        return self.kinematics.position_history

    @property
    def footprint(self) -> Vertex:
        return self.kinematics.footprint

    @property
    def previous_footprint(self) -> Optional[Vertex]:
        return self.kinematics.previous_footprint

    @property
    def footprint_left(self) -> Vertex:
        return self.kinematics.footprint_left

    @property
    def previous_footprint_left(self) -> Optional[Vertex]:
        return self.kinematics.previous_footprint_left

    @property
    def footprint_right(self) -> Vertex:
        return self.kinematics.footprint_right

    @property
    def previous_footprint_right(self) -> Optional[Vertex]:
        return self.kinematics.previous_footprint_right

    @property
    def stationary_frames(self) -> int:
        return self.kinematics.stationary_frames

    @property
    def active_violations(self) -> set:
        return self.violation_state.active_violations

    def update_position(
        self, 
        new_centroid: Vertex, 
        new_footprint_center: Vertex, 
        new_footprint_left: Vertex, 
        new_footprint_right: Vertex
    ) -> None:
        self.kinematics.update_position(new_centroid, new_footprint_center, new_footprint_left, new_footprint_right)

    def is_moving(self, movement_threshold: float = 0.7) -> bool:
        return self.kinematics.is_moving(movement_threshold)


class VehicleManager:
    def __init__(self, max_lost_frames: int = 30):
        self.max_lost_frames = max_lost_frames
        self._active_vehicles: Dict[int, Vehicle] = {}
        self._lost_tracks: Dict[int, int] = {}

    def process_frame_detections(
        self, 
        detections: List[Tuple[int, TrafficVehicleType, Vertex, Vertex, Vertex, Vertex]]
    ) -> List[Vehicle]:
        seen_this_frame = set()

        for track_id, v_type, current_centroid, current_footprint, current_left, current_right in detections:
            t_id = int(track_id)
            seen_this_frame.add(t_id)
            if self.is_new_vehicle(t_id):
                self.add_vehicle(
                    vehicle_id= t_id,
                    vehicle_type= v_type,
                    current_centroid= current_centroid,
                    current_footprint= current_footprint,
                    current_left= current_left,
                    current_right= current_right
                )
            else:
                self.update_vehicle(
                    vehicle_id= t_id,
                    current_centroid= current_centroid,
                    current_footprint= current_footprint,
                    current_left= current_left,
                    current_right= current_right
                )

        active_track_ids = list(self._active_vehicles.keys()) 
        
        for t_id in active_track_ids:
            if t_id not in seen_this_frame:
                self._lost_tracks[t_id] += 1
                if self._lost_tracks[t_id] > self.max_lost_frames:
                    self.del_vehicle(t_id)

        return [self._active_vehicles[t_id] for t_id in seen_this_frame]
    
    def is_new_vehicle(self, vehicle_id: int) -> bool:
        return int(vehicle_id) not in self._active_vehicles
    
    def add_vehicle(
        self, 
        vehicle_id: int, 
        vehicle_type: TrafficVehicleType, 
        current_centroid: Vertex, 
        current_footprint: Vertex, 
        current_left: Vertex, 
        current_right: Vertex
    ) -> None:
        v_id = int(vehicle_id)
        new_vehicle = Vehicle(
            track_id=v_id, 
            vehicle_type=vehicle_type, 
            initial_centroid=current_centroid,
            initial_footprint_center=current_footprint,
            initial_footprint_left=current_left,
            initial_footprint_right=current_right
        )
        self._active_vehicles[v_id] = new_vehicle
        self._lost_tracks[v_id] = 0

    def update_vehicle(
        self, 
        vehicle_id: int, 
        current_centroid: Vertex, 
        current_footprint: Vertex, 
        current_left: Vertex, 
        current_right: Vertex
    ) -> None:
        v_id = int(vehicle_id)
        self._active_vehicles[v_id].update_position(current_centroid, current_footprint, current_left, current_right)
        self._lost_tracks[v_id] = 0

    def del_vehicle(self, vehicle_id: int) -> None:
        v_id = int(vehicle_id)
        self._active_vehicles[v_id].violation_state.clear()
        del self._active_vehicles[v_id]
        del self._lost_tracks[v_id]

    def get_all_active_vehicles(self) -> List[Vehicle]:
        return list(self._active_vehicles.values())

    def get_vehicle(self, track_id: int) -> Optional[Vehicle]:
        return self._active_vehicles.get(track_id)

class VehicleRecord:
    pass