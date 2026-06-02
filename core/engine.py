import logging
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
#from core.trafficlight import TrafficLight TODO

logger = logging.getLogger("RuleEngine")
logger.setLevel(logging.INFO)

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
            if lane is not None:
                wrong_way_event = ViolationRuleEngine._evaluate_wrong_way(vehicle, lane)
                if wrong_way_event: violations.append(wrong_way_event)

                line_crossing_event = ViolationRuleEngine._evaluate_line_crossing(vehicle, lane)
                if line_crossing_event: violations.append(line_crossing_event)

                wrong_lane_event = ViolationRuleEngine._evaluate_wrong_lane(vehicle, lane)
                if wrong_lane_event: violations.append(wrong_lane_event)
        else:
            illegal_parking_event = ViolationRuleEngine._evaluate_illegal_parking(vehicle, safe_zones, safe_time)
            if illegal_parking_event: violations.append(illegal_parking_event)

            pedestrian_stop_event = ViolationRuleEngine._evaluate_pedestrian_stop(vehicle, safe_zones)
            if pedestrian_stop_event: violations.append(pedestrian_stop_event)

        return violations

    @staticmethod
    def _evaluate_wrong_way(vehicle: Vehicle, lane: TrafficLane) -> Optional[ViolationEvent]:
        if ViolationRuleEngine._check_wrong_direction(vehicle, lane):
            if ViolationType.WRONG_WAY not in vehicle.active_violations:
                vehicle.active_violations.add(ViolationType.WRONG_WAY)
                return ViolationEvent(vehicle.id, ViolationType.WRONG_WAY)
        return None

    @staticmethod
    def _evaluate_line_crossing(vehicle: Vehicle, lane: TrafficLane) -> Optional[ViolationEvent]:
        is_crossing_solid_line = False
        # Check if vehicle is CAR/ TRUCK/ BUS/ CONTAINER
        is_4_wheeler = vehicle.vehicle_type in [
            TrafficVehicleType.CAR, 
            TrafficVehicleType.TRUCK, 
            TrafficVehicleType.BUS, 
            TrafficVehicleType.CONTAINER
        ]

        # Looping through edge that is SOLID
        for edge in lane.solid_edges:
            # If vehicle is four wheels
            if is_4_wheeler:
                if vehicle.previous_footprint_left and vehicle.previous_footprint_right:
                    # If vehicle move cross the line with left/ right tire
                    """
                    VISUALIZE:
                    current left/ right tire coordinate | 
                                                        | previous left/ right tire coordinate
                                                        |

                    """
                    crossed_left = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_left, vehicle.footprint_left,
                        edge.p1, edge.p2
                    )
                    
                    crossed_right = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_right, vehicle.footprint_right,
                        edge.p1, edge.p2
                    )
                    
                    # If vehicle NOT crossing the line BUT already ON it and move forward
                    """
                    VISUALIZE:
                    current left tire coordinate    | 
                                                    | curent right tire coordinate
                                                    |
                    """
                    straddling_line = SpatialMath.do_segments_intersect(
                        vehicle.footprint_left, vehicle.footprint_right,
                        edge.p1, edge.p2
                    )
                    if crossed_left or crossed_right or straddling_line:
                        is_crossing_solid_line = True
                        break
            else:
                # If vehicle is two wheels
                if vehicle.previous_routing_point:
                    # Do segment intersect with vehicle's tire as "routing_point"
                    if SpatialMath.do_segments_intersect(
                        vehicle.previous_routing_point, vehicle.routing_point,
                        edge.p1, edge.p2
                    ):
                        is_crossing_solid_line = True
                        break

        if is_crossing_solid_line:
            # Add violation type to vehicle's violation record
            if ViolationType.LINE_CROSSING not in vehicle.active_violations:
                vehicle.active_violations.add(ViolationType.LINE_CROSSING)
                return ViolationEvent(vehicle.id, ViolationType.LINE_CROSSING)
        return None

    @staticmethod
    def _evaluate_wrong_lane(vehicle: Vehicle, lane: TrafficLane) -> Optional[ViolationEvent]:
        # If vehicle is inside a lane AND vehicle type is not allowed
        is_inside_lane = is_vehicle_inside(lane, vehicle.routing_point)
        is_wrong_lane = not is_vehicle_allowed(lane, vehicle.vehicle_type)

        if is_inside_lane and is_wrong_lane:
            # Add violation to vehicle's violation record
            if ViolationType.WRONG_LANE not in vehicle.active_violations:
                vehicle.active_violations.add(ViolationType.WRONG_LANE)
                return ViolationEvent(vehicle.id, ViolationType.WRONG_LANE)
        return None

    @staticmethod
    def _evaluate_illegal_parking(vehicle: Vehicle, zones: List[TrafficZone], 
                                current_time: datetime,
                                source_fps: int =  24,
                                allowed_time_second: int = 300) -> Optional[ViolationEvent]:
        # If vehicle have not moving for a period of time
        if vehicle.stationary_frames < allowed_time_second * source_fps:
            return None
        # If NO_PARKING zone is active
        for zone in zones:
            if zone.zone_type == TrafficZoneType.NO_PARKING and zone.is_currently_active(current_time):
                if ViolationType.ILLEGAL_PARKING not in vehicle.active_violations:
                    vehicle.active_violations.add(ViolationType.ILLEGAL_PARKING)
                    return ViolationEvent(vehicle.id, ViolationType.ILLEGAL_PARKING)
        return None

    @staticmethod
    def _evaluate_pedestrian_stop(vehicle: Vehicle, zones: List[TrafficZone],
                                  source_fps: int = 24,
                                  allowed_time_second: int = 300) -> Optional[ViolationEvent]:
        if vehicle.stationary_frames < allowed_time_second * source_fps:
            return None
        for zone in zones:
            if zone.zone_type == TrafficZoneType.PEDESTRIAN_CROSSING:
                if ViolationType.PEDESTRIAN_CROSSING_STOP not in vehicle.active_violations:
                    vehicle.active_violations.add(ViolationType.PEDESTRIAN_CROSSING_STOP)
                    return ViolationEvent(vehicle.id, ViolationType.PEDESTRIAN_CROSSING_STOP)
        return None

    @staticmethod
    def _check_wrong_direction(vehicle: Vehicle, lane: TrafficLane) -> bool:
        if not vehicle.previous_position:
            return False
            
        d_current = get_distance_to_start(lane, vehicle.current_position)
        d_prev = get_distance_to_start(lane, vehicle.previous_position)
        
        is_distance_decreasing = (d_current - d_prev) < -0.2
        is_vector_opposed = vehicle.direction.dot_product(lane.lane_direction) < 0
        return is_distance_decreasing and is_vector_opposed
    @staticmethod
    def _evaluate_red_light_running(
        vehicle: Vehicle, traffic_lights
    ) -> Optional[ViolationEvent]:
        #TODO
        return None