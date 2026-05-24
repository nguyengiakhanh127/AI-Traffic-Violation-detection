from typing import List, Optional, Tuple
from datetime import datetime
from utils.enums import TrafficLineType, ViolationType, TrafficZoneType, TrafficVehicleType
from geometry.shapes import Edge        
from geometry.spatial_math import SpatialMath 
from core.lane import (
    TrafficLane, 
    TrafficZone,
    get_distance_to_start, 
    is_vehicle_inside, 
    is_vehicle_allowed
)
from core.rules import ViolationRegistry
from core.vehicle import Vehicle


class ViolationEvent:
    def __init__(self, vehicle_id: int, violation_type: ViolationType):
        self.vehicle_id = vehicle_id
        self.violation_type = violation_type
        
        self.error_name: str = ViolationRegistry.get_code(violation_type)
        self.description: str = ViolationRegistry.get_description(violation_type)

    def __repr__(self):
        return f"[VIOLATION] Xe {self.vehicle_id} - Lỗi: {self.error_name} ({self.description})"


class ViolationRuleEngine:
    
    @staticmethod
    def inspect_vehicle(
        vehicle: Vehicle, 
        lane: Optional[TrafficLane], 
        zones: Optional[List[TrafficZone]] = None,    
        current_time: Optional[datetime] = None       
    ) -> List[ViolationEvent]:
        violations = []

        safe_zones = zones if zones is not None else []
        safe_time = current_time if current_time is not None else datetime.now()

        if vehicle.is_moving(movement_threshold=1.0):
            
            # --- NHÓM 1: VI PHẠM KHI DI CHUYỂN (MOVING VIOLATIONS) ---
            
            if lane is not None:
                # Đi ngược chiều
                wrong_way_event = ViolationRuleEngine._evaluate_wrong_way(vehicle, lane)
                if wrong_way_event:
                    violations.append(wrong_way_event)

                # Đè vạch phân làn
                line_crossing_event = ViolationRuleEngine._evaluate_line_crossing(vehicle, lane)
                if line_crossing_event:
                    violations.append(line_crossing_event)

                # Đi sai làn đường
                wrong_lane_event = ViolationRuleEngine._evaluate_wrong_lane(vehicle, lane)
                if wrong_lane_event:
                    violations.append(wrong_lane_event)

            # Đi vào đường cấm - #TODO
            """
            forbidden_entry_event = ViolationRuleEngine._evaluate_forbidden_entry(vehicle, safe_zones, safe_time)
            if forbidden_entry_event:
                violations.append(forbidden_entry_event)
            """
                
        else:
            
            # --- NHÓM 2: VI PHẠM KHI DỪNG ĐỖ TĨNH (STATIONARY VIOLATIONS) ---
            
            # Đỗ xe trái quy định
            illegal_parking_event = ViolationRuleEngine._evaluate_illegal_parking(vehicle, safe_zones, safe_time)
            if illegal_parking_event:
                violations.append(illegal_parking_event)

            # Dừng xe ngay vạch đi bộ
            pedestrian_stop_event = ViolationRuleEngine._evaluate_pedestrian_stop(vehicle, safe_zones)
            if pedestrian_stop_event:
                violations.append(pedestrian_stop_event)

        return violations


    @staticmethod
    def _evaluate_wrong_way(vehicle: Vehicle, lane: TrafficLane) -> Optional[ViolationEvent]:
        current_wrong_way = ViolationRuleEngine._check_wrong_direction(vehicle, lane)
        if current_wrong_way:
            if ViolationType.WRONG_WAY not in vehicle.active_violations:
                vehicle.active_violations.add(ViolationType.WRONG_WAY)
                return ViolationEvent(vehicle.track_id, ViolationType.WRONG_WAY)
        return None


    @staticmethod
    def _evaluate_line_crossing(vehicle: Vehicle, lane: TrafficLane) -> Optional[ViolationEvent]:
        is_crossing_solid_line = False

        is_4_wheeler = vehicle.vehicle_type in [
            TrafficVehicleType.CAR, 
            TrafficVehicleType.TRUCK, 
            TrafficVehicleType.BUS, 
            TrafficVehicleType.CONTAINER
        ]
        #TODO
        if is_4_wheeler:
            for edge in lane.solid_edges:
                """
                crossed_instant = SpatialMath.do_segments_intersect(
                    vehicle.footprint_left,
                    vehicle.footprint_right,
                    edge.p1,
                    edge.p2
                )
                if crossed_instant:
                    is_crossing_solid_line = True
                    break
                
                if vehicle.previous_footprint_left and vehicle.previous_footprint_right:
                    crossed_left = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_left,
                        vehicle.footprint_left,
                        edge.p1,
                        edge.p2
                    )
                    crossed_right = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_right,
                        vehicle.footprint_right,
                        edge.p1,
                        edge.p2
                    )
                    if crossed_left or crossed_right:
                        is_crossing_solid_line = True
                        break
                    """
                if vehicle.previous_footprint:
                    for edge in lane.solid_edges:
                        if SpatialMath.do_segments_intersect(
                            vehicle.previous_footprint,
                            vehicle.footprint,
                            edge.p1,
                            edge.p2
                        ):
                            is_crossing_solid_line = True
                            break
        else:
            if vehicle.previous_footprint:
                for edge in lane.solid_edges:
                    if SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint,
                        vehicle.footprint,
                        edge.p1,
                        edge.p2
                    ):
                        is_crossing_solid_line = True
                        break

        event = None
        if is_crossing_solid_line:
            if ViolationType.LINE_CROSSING not in vehicle.active_violations:
                vehicle.active_violations.add(ViolationType.LINE_CROSSING)
                event = ViolationEvent(vehicle.track_id, ViolationType.LINE_CROSSING)
                
        return event


    @staticmethod
    def _evaluate_wrong_lane(vehicle: Vehicle, lane: TrafficLane) -> Optional[ViolationEvent]:
        is_inside_lane = is_vehicle_inside(lane, vehicle.footprint)
        is_wrong_lane = not is_vehicle_allowed(lane, vehicle.vehicle_type)

        if is_inside_lane and is_wrong_lane:
            if ViolationType.WRONG_LANE not in vehicle.active_violations:
                vehicle.active_violations.add(ViolationType.WRONG_LANE)
                return ViolationEvent(vehicle.track_id, ViolationType.WRONG_LANE)
                
        return None

    """
    @staticmethod
    def _evaluate_forbidden_entry(
        vehicle: Vehicle, 
        zones: List[TrafficZone],
        current_time: datetime
    ) -> Optional[ViolationEvent]:
        for zone in zones:
            if zone.zone_type == TrafficZoneType.FORBIDDEN_AREA:
                if zone.is_currently_active(current_time):
                    if ViolationType.FORBIDDEN_ENTRY not in vehicle.active_violations:
                        vehicle.active_violations.add(ViolationType.FORBIDDEN_ENTRY)
                        return ViolationEvent(vehicle.track_id, ViolationType.FORBIDDEN_ENTRY)
        return None

    """

    @staticmethod
    def _evaluate_illegal_parking(
        vehicle: Vehicle, 
        zones: List[TrafficZone],
        current_time: datetime,
        allowed_stationary_frames: int = 10
    ) -> Optional[ViolationEvent]:
        if vehicle.stationary_frames < allowed_stationary_frames:
            return None

        for zone in zones:
            if zone.zone_type == TrafficZoneType.NO_PARKING:
                if zone.is_currently_active(current_time):
                    if ViolationType.ILLEGAL_PARKING not in vehicle.active_violations:
                        vehicle.active_violations.add(ViolationType.ILLEGAL_PARKING)
                        return ViolationEvent(vehicle.track_id, ViolationType.ILLEGAL_PARKING)
        return None


    @staticmethod
    def _evaluate_pedestrian_stop(vehicle: Vehicle, zones: List[TrafficZone]) -> Optional[ViolationEvent]:
        if vehicle.stationary_frames < 90:
            return None

        for zone in zones:
            if zone.zone_type == TrafficZoneType.PEDESTRIAN_CROSSING:
                if ViolationType.PEDESTRIAN_CROSSING_STOP not in vehicle.active_violations:
                    vehicle.active_violations.add(ViolationType.PEDESTRIAN_CROSSING_STOP)
                    return ViolationEvent(vehicle.track_id, ViolationType.PEDESTRIAN_CROSSING_STOP)
        return None

    @staticmethod
    def _check_wrong_direction(vehicle: Vehicle, lane: TrafficLane) -> bool:
        if not vehicle.previous_position:
            return False
        print(f"----------")
        print(vehicle.current_position)
        print(vehicle.previous_position)
        print(f"**********")
        d_current = get_distance_to_start(lane, vehicle.current_position)
        d_prev = get_distance_to_start(lane, vehicle.previous_position)
        
        is_distance_decreasing = (d_current - d_prev) < -0.2
        is_vector_opposed = vehicle.direction.dot_product(lane.lane_direction) < 0
        print(d_current)
        print(d_prev)
        print(is_distance_decreasing)
        print(is_vector_opposed)
        return is_distance_decreasing and is_vector_opposed

# --- END OF FILE engine.py ---