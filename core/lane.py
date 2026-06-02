from dataclasses import dataclass
from datetime import datetime
from utils.enums import TrafficVehicleType, TrafficZoneType
from geometry.primitives import Vertex, Vector2D
from geometry.shapes import Edge, Polygon
from core.rules import TrafficLaneRule
from core.vehicle import  Vehicle
from typing import List, Optional, Tuple
from geometry.spatial_math import SpatialMath
from utils.enums import TrafficLineType
import math

class TrafficLane:
    def __init__(
        self,
        lane_id: str,
        edges: List[Edge],
        lane_rule: TrafficLaneRule
    ):
        self.lane_id = lane_id
        self.edges = edges
        self.lane_rule = lane_rule
        
        # Điểm xuất phát và Vector hướng được tính toán tự động bằng thuật toán mới
        self.entry_point = self._setup_entry_point()
        self.lane_direction = self._setup_lane_direction()
        
        self.polygon = Polygon([edge.p1 for edge in self.edges])
        self.solid_edges: List[Edge] = [e for e in self.edges if e.line_type == TrafficLineType.SOLID]

class TrafficLane:
    def __init__(
        self,
        lane_id: str,
        edges: List[Edge],
        lane_rule: TrafficLaneRule
    ):
        self.lane_id = lane_id
        self.edges = edges
        self.lane_rule = lane_rule
        
        # Thiết lập điểm vào và hướng bằng thuật toán Midpoint (Nguyên bản)
        self.entry_point = self._setup_entry_point()
        self.lane_direction = self._setup_lane_direction()
        
        self.polygon = Polygon([edge.p1 for edge in self.edges])
        
        self.solid_edges: List[Edge] = [e for e in self.edges if e.line_type == TrafficLineType.SOLID]

    def _setup_entry_point(self) -> Vertex:
        """
        [Khôi phục]: Tìm điểm xuất phát bằng trung điểm (Midpoint) của cạnh ENTRY.
        Giả định người dùng vẽ 1 cạnh ENTRY duy nhất cắt ngang lối vào.
        """
        entry_edges = [e for e in self.edges if e.line_type == TrafficLineType.ENTRY]
        if entry_edges:
            return SpatialMath.get_midpoint(entry_edges[0])
        
        return self.edges[0].p1 # Fallback an toàn
    
    def _setup_lane_direction(self) -> Vector2D:
        """
        [Khôi phục]: Xác định hướng làn đường bằng cách nối trung điểm (Midpoint) 
        của cạnh ENTRY đến trung điểm của cạnh EXIT.
        Giả định làn đường là một tứ giác (Quadrilateral) có 2 vạch ngang tiêu chuẩn.
        """
        entry_edges = [e for e in self.edges if e.line_type == TrafficLineType.ENTRY]
        exit_edges = [e for e in self.edges if e.line_type == TrafficLineType.EXIT]
        
        if entry_edges and exit_edges:
            entry_mid = SpatialMath.get_midpoint(entry_edges[0])
            exit_mid = SpatialMath.get_midpoint(exit_edges[0])
            
            # Trả về Vector chuẩn hóa nối từ điểm Vào đến điểm Ra
            return SpatialMath.get_normalized_vector(entry_mid, exit_mid)
            
        return Vector2D(0.0, -1.0) # Fallback hướng lên trên


    def get_line_crossed(self, vehicle_pos: Vertex, epsilon_pixels: float = 2.0) -> Optional[Edge]:
        px, py = vehicle_pos.x, vehicle_pos.y
        
        for edge in self.edges:
            x1, y1 = edge.p1.x, edge.p1.y
            x2, y2 = edge.p2.x, edge.p2.y
            
            dx, dy = x2 - x1, y2 - y1
            if dx == 0 and dy == 0:
                continue
                
            l2 = dx*dx + dy*dy
            
            t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))

            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            
            distance = math.hypot(px - proj_x, py - proj_y)
            
            if distance <= epsilon_pixels:
                return edge
                
        return None

def is_vehicle_inside(lane: TrafficLane, vehicle_pos: Vertex) -> bool:
    return lane.polygon.is_contain_point(vehicle_pos)

def is_vehicle_allowed(lane: TrafficLane, vehicle_type: 'TrafficVehicleType') -> bool:
    return lane.lane_rule.is_allowed(vehicle_type)

def get_distance_to_start(lane: TrafficLane, vehicle_pos: Vertex) -> float:
    return SpatialMath.calculate_distance(vehicle_pos, lane.entry_point)

@dataclass
class TrafficZone:
    zone_id: str
    zone_type: TrafficZoneType
    polygon: Polygon
    
    prohibited_hours: Optional[Tuple[int, int]] = None
    prohibited_days: Optional[str] = None           

    def is_point_inside(self, point: Vertex) -> bool:
        return self.polygon.is_contain_point(point)

    def is_currently_active(self, current_time: datetime) -> bool:
        if self.zone_type != TrafficZoneType.NO_PARKING:
            return True

        day_of_month = current_time.day
        if self.prohibited_days == "ODD" and day_of_month % 2 == 0:
            return False  
        if self.prohibited_days == "EVEN" and day_of_month % 2 != 0:
            return False  
        
        if self.prohibited_hours:
            start_hour, end_hour = self.prohibited_hours
            current_hour = current_time.hour
            if not (start_hour <= current_hour < end_hour):
                return False  

        return True  


class LaneManager:
    def __init__(self, lanes: List[TrafficLane]):
        self.lanes = lanes

    def get_lane_at_position(self, position: Vertex) -> Optional[TrafficLane]:
        for lane in self.lanes:
            if is_vehicle_inside(lane, position):
                return lane
        return None

    def get_lanes_at_position(self, position: Vertex) -> List[TrafficLane]:
        matched_lanes = []
        for lane in self.lanes:
            if is_vehicle_inside(lane, position):
                matched_lanes.append(lane)
        return matched_lanes

    def get_routing_lanes(self, vehicle: 'Vehicle') -> List[TrafficLane]:
        routing_lanes = set()
        
        current_lane = self.get_lane_at_position(vehicle.footprint)
        if current_lane:
            routing_lanes.add(current_lane)
            
        if vehicle.previous_footprint:
            previous_lane = self.get_lane_at_position(vehicle.previous_footprint)
            if previous_lane:
                routing_lanes.add(previous_lane)
                
        return list(routing_lanes)

class ZoneManager:
    def __init__(self, zones: List[TrafficZone]):
        self.zones = zones

    def get_zones_at_position(self, position: Vertex) -> List[TrafficZone]:
        matched_zones = []
        for zone in self.zones:
            if zone.is_point_inside(position):
                matched_zones.append(zone)
        return matched_zones
