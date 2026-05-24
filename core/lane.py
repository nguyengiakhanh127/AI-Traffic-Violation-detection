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
        
        self.entry_point = self._setup_entry_point()
        self.lane_direction = self._setup_lane_direction()
        
        self.polygon = Polygon([edge.p1 for edge in self.edges])
        
        self.solid_edges: List[Edge] = [e for e in self.edges if e.line_type == TrafficLineType.SOLID]

    def _setup_entry_point(self) -> Vertex:
        virtual_edges = [e for e in self.edges if e.line_type == TrafficLineType.VIRTUAL]
        if virtual_edges:
            return SpatialMath.get_midpoint(virtual_edges[0])
        
        return self.edges[0].p1 
    
    def _setup_lane_direction(self) -> Vector2D:
        virtual_edges = [e for e in self.edges if e.line_type == TrafficLineType.VIRTUAL]
        if len(virtual_edges) >= 2:
            entry_mid = SpatialMath.get_midpoint(virtual_edges[0])
            exit_mid  = SpatialMath.get_midpoint(virtual_edges[1])
            return SpatialMath.get_normalized_vector(entry_mid, exit_mid)
            
        return Vector2D(0.0, -1.0) 

    def get_line_crossed(self, vehicle_pos: Vertex, epsilon_pixels: float = 2.0) -> Optional[Edge]:
        for edge in self.edges:
            if edge.norm == 0:
                continue
                
            numerator = abs(SpatialMath.get_relative_position(vehicle_pos, edge))
            distance = numerator / edge.norm
            
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
