import logging
from typing import List, Optional
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from utils.enums import TrafficLineType, ViolationType, TrafficZoneType, TrafficLightColor
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
from core.trafficlight import TrafficLight

logger = logging.getLogger("RuleEngine")
logger.setLevel(logging.INFO)

# ==========================================
# 1. MODELS & CONTEXT (Dữ liệu & Bối cảnh)
# ==========================================

class ViolationEvent:
    def __init__(self, vehicle_id: int, violation_type: ViolationType):
        self.vehicle_id = vehicle_id
        self.violation_type = violation_type
        self.error_name: str = ViolationRegistry.get_code(violation_type)
        self.description: str = ViolationRegistry.get_description(violation_type)

    def __repr__(self):
        return f"[VIOLATION] Xe {self.vehicle_id} - Lỗi: {self.error_name} ({self.description})"

@dataclass
class InspectionContext:
    """Đóng gói toàn bộ bối cảnh không gian và thời gian tại thời điểm kiểm tra"""
    lane: Optional[TrafficLane] = None
    zones: List[TrafficZone] = field(default_factory=list)
    current_time: datetime = field(default_factory=datetime.now)
    traffic_lights: List['TrafficLight'] = field(default_factory=list)


# ==========================================
# 2. BASE RULE (Lớp trừu tượng nền tảng)
# ==========================================

class BaseViolationRule(ABC):
    """Lớp nền tảng cho mọi thuật toán bắt lỗi vi phạm"""
    @abstractmethod
    def evaluate(self, vehicle: Vehicle, context: InspectionContext) -> Optional[ViolationEvent]:
        pass

    def _register_violation(self, vehicle: Vehicle, violation_type: ViolationType) -> Optional[ViolationEvent]:
        """Hàm tiện ích giúp ghi nhận vi phạm để tránh bắt trùng lặp liên tục"""
        if violation_type not in vehicle.active_violations:
            vehicle.active_violations.add(violation_type)
            return ViolationEvent(vehicle.id, violation_type)
        return None


# ==========================================
# 3. CONCRETE RULES (Các luật cụ thể)
# ==========================================

class WrongWayRule(BaseViolationRule):
    def evaluate(self, vehicle: Vehicle, context: InspectionContext) -> Optional[ViolationEvent]:
        if not vehicle.is_moving(threshold=2.0) or not context.lane:
            return None
        if not vehicle.previous_position:
            return None
            
        d_current = get_distance_to_start(context.lane, vehicle.current_position)
        d_prev = get_distance_to_start(context.lane, vehicle.previous_position)
        
        is_distance_decreasing = (d_current - d_prev) < -0.2
        is_vector_opposed = vehicle.direction.dot_product(context.lane.lane_direction) < 0
        
        if is_distance_decreasing and is_vector_opposed:
            return self._register_violation(vehicle, ViolationType.WRONG_WAY)
        return None

class LineCrossingRule(BaseViolationRule):
    def evaluate(self, vehicle: Vehicle, context: InspectionContext) -> Optional[ViolationEvent]:
        if not vehicle.is_moving(threshold=2.0) or not context.lane:
            return None

        is_crossing_solid_line = False

        for edge in context.lane.solid_edges:
            # Duck Typing: Nếu xe có 2 vệt bánh (Footprints) -> Kiểm tra theo logic 4 bánh
            if vehicle.footprint_left and vehicle.footprint_right:
                if vehicle.previous_footprint_left and vehicle.previous_footprint_right:
                    crossed_left = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_left, vehicle.footprint_left, edge.p1, edge.p2
                    )
                    crossed_right = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_right, vehicle.footprint_right, edge.p1, edge.p2
                    )
                    straddling_line = SpatialMath.do_segments_intersect(
                        vehicle.footprint_left, vehicle.footprint_right, edge.p1, edge.p2
                    )
                    if crossed_left or crossed_right or straddling_line:
                        is_crossing_solid_line = True
                        break
            
            # Ngược lại: Nếu xe chỉ có điểm định tuyến (routing_point) -> Kiểm tra theo logic 2 bánh
            else:
                if vehicle.previous_routing_point:
                    if SpatialMath.do_segments_intersect(
                        vehicle.previous_routing_point, vehicle.routing_point, edge.p1, edge.p2
                    ):
                        is_crossing_solid_line = True
                        break

        if is_crossing_solid_line:
            return self._register_violation(vehicle, ViolationType.LINE_CROSSING)
        return None

class WrongLaneRule(BaseViolationRule):
    def evaluate(self, vehicle: Vehicle, context: InspectionContext) -> Optional[ViolationEvent]:
        if not vehicle.is_moving(threshold=2.0) or not context.lane:
            return None

        is_inside_lane = is_vehicle_inside(context.lane, vehicle.routing_point)
        is_wrong_lane = not is_vehicle_allowed(context.lane, vehicle.vehicle_type)

        if is_inside_lane and is_wrong_lane:
            return self._register_violation(vehicle, ViolationType.WRONG_LANE)
        return None

class IllegalParkingRule(BaseViolationRule):
    def __init__(self, source_fps: int = 24, allowed_time_second: int = 300):
        self.source_fps = source_fps
        self.allowed_time_second = allowed_time_second

    def evaluate(self, vehicle: Vehicle, context: InspectionContext) -> Optional[ViolationEvent]:
        if vehicle.is_moving(threshold=1.0) or not context.zones:
            return None

        if vehicle.stationary_frames < self.allowed_time_second * self.source_fps:
            return None

        for zone in context.zones:
            if zone.zone_type == TrafficZoneType.NO_PARKING and zone.is_currently_active(context.current_time):
                return self._register_violation(vehicle, ViolationType.ILLEGAL_PARKING)
        return None

class PedestrianStopRule(BaseViolationRule):
    def __init__(self, source_fps: int = 24, allowed_time_second: int = 300):
        self.source_fps = source_fps
        self.allowed_time_second = allowed_time_second

    def evaluate(self, vehicle: Vehicle, context: InspectionContext) -> Optional[ViolationEvent]:
        if vehicle.is_moving(threshold=1.0) or not context.zones:
            return None

        if vehicle.stationary_frames < self.allowed_time_second * self.source_fps:
            return None

        for zone in context.zones:
            if zone.zone_type == TrafficZoneType.PEDESTRIAN_CROSSING:
                return self._register_violation(vehicle, ViolationType.PEDESTRIAN_CROSSING_STOP)
        return None

class RedLightRunningRule(BaseViolationRule):
    def evaluate(self, vehicle: Vehicle, context: InspectionContext) -> Optional[ViolationEvent]:
        # Nếu xe đang đứng yên hoặc không có đèn giao thông nào được cấu hình -> Bỏ qua
        if not vehicle.is_moving() or not context.traffic_lights:
            return None

        for light in context.traffic_lights:
            # Chỉ bắt lỗi khi đèn ĐANG ĐỎ
            if light.current_color != TrafficLightColor.RED:
                continue

            # Sử dụng "Duck Typing" toán học để xem bánh xe/trọng tâm có đè qua vạch Stop line không
            is_crossing_stop_line = False
            
            # Logic xe 4 bánh
            if vehicle.footprint_left and vehicle.footprint_right:
                if vehicle.previous_footprint_left and vehicle.previous_footprint_right:
                    crossed_left = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_left, vehicle.footprint_left, light.stop_line.p1, light.stop_line.p2
                    )
                    crossed_right = SpatialMath.do_segments_intersect(
                        vehicle.previous_footprint_right, vehicle.footprint_right, light.stop_line.p1, light.stop_line.p2
                    )
                    if crossed_left or crossed_right:
                        is_crossing_stop_line = True
            # Logic xe 2 bánh
            else:
                if vehicle.previous_routing_point:
                    if SpatialMath.do_segments_intersect(
                        vehicle.previous_routing_point, vehicle.routing_point, light.stop_line.p1, light.stop_line.p2
                    ):
                        is_crossing_stop_line = True

            # Kiểm tra ngoại lệ: Nếu xe rẽ phải và có vạch cho phép rẽ phải
            if is_crossing_stop_line and light.right_turn_line:
                # Nếu hướng xe di chuyển cắt qua vạch rẽ phải -> Tha mạng (Return None)
                # (Bạn có thể bổ sung logic check rẽ phải ở đây nếu cần)
                pass 

            if is_crossing_stop_line:
                return self._register_violation(vehicle, ViolationType.RED_LIGHT_RUNNING)
                
        return None


# ==========================================
# 4. ENGINE (Bộ máy thực thi)
# ==========================================

class ViolationRuleEngine:
    def __init__(self):
        self._rules: List[BaseViolationRule] = []

    def add_rule(self, rule: BaseViolationRule):
        """Đăng ký một luật vi phạm vào Engine"""
        self._rules.append(rule)

    def remove_rule(self, rule_class: type):
        """Xóa một luật khỏi Engine dựa trên class"""
        self._rules = [r for r in self._rules if not isinstance(r, rule_class)]

    def inspect_vehicle(self, vehicle: Vehicle, context: InspectionContext) -> List[ViolationEvent]:
        """Đánh giá phương tiện dựa trên tất cả các luật đã đăng ký"""
        violations = []
        for rule in self._rules:
            event = rule.evaluate(vehicle, context)
            if event:
                violations.append(event)
        return violations