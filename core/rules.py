# --- START OF FILE core/rules.py ---

from typing import Set, Dict
from utils.enums import TrafficVehicleType, ViolationType

class TrafficLaneRule:
    def __init__(self, allowed_vehicles: Set['TrafficVehicleType']):
        self.allowed_vehicles = allowed_vehicles

    def is_allowed(self, vehicle_type: 'TrafficVehicleType') -> bool:
        return vehicle_type in self.allowed_vehicles

class ViolationRegistry:
    _METADATA: Dict[ViolationType, Dict[str, str]] = {
        ViolationType.WRONG_LANE: {
            "code": "DI_SAI_LAN",
            "desc": "Đi không đúng làn đường quy định cho từng loại phương tiện",
            "name": "Đi sai làn"
        },
        ViolationType.LINE_CROSSING: {
            "code": "DE_VACH_PHAN_LAN",
            "desc": "Không chấp hành hiệu lệnh, chỉ dẫn của vạch kẻ đường",
            "name": "Đè vạch phân làn"
        },
        ViolationType.WRONG_WAY: {
            "code": "DI_NGUOC_CHIEU",
            "desc": "Đi ngược chiều của đường một chiều hoặc đường có biển cấm",
            "name": "Đi ngược chiều"
        },
        ViolationType.FORBIDDEN_ENTRY: {
            "code": "VAO_DUONG_CAM",
            "desc": "Đi vào khu vực cấm, đường có biển báo hiệu cấm đi vào",
            "name": "Đi vào đường cấm"
        },
        ViolationType.ILLEGAL_PARKING: {
            "code": "DUNG_DO_TRAI_QUY_DINH",
            "desc": "Dừng xe, đỗ xe trái quy định của pháp luật đường bộ",
            "name": "Dừng đỗ trái phép"
        },
        ViolationType.PEDESTRIAN_CROSSING_STOP: {
            "code": "DO_TREN_VACH_DI_BO",
            "desc": "Dừng xe, đỗ xe đè lên vạch kẻ đường dành cho người đi bộ",
            "name": "Đỗ đè vạch đi bộ" 
        },
        ViolationType.RED_LINE: {
            "code": "VUOT_DEN_DO",
            "desc": "Không chấp hành tín hiệu đèn giao thông",
            "name": "Vượt đèn đỏ" 
        }
    }

    @classmethod
    def get_code(cls, violation_type: ViolationType) -> str:
        return cls._METADATA.get(violation_type, {}).get("code", "UNKNOWN")

    @classmethod
    def get_description(cls, violation_type: ViolationType) -> str:
        return cls._METADATA.get(violation_type, {}).get("desc", "Không xác định")

    @classmethod
    def get_name(cls, violation_type: ViolationType) -> str:
        return cls._METADATA.get(violation_type, {}).get("name", "Lỗi không xác định")
        
    @classmethod
    def get_all_for_ui(cls) -> list:
        return [(meta.get("name"), meta.get("code")) for meta in cls._METADATA.values()]

class VehicleRegistry:
    _UI_NAMES = {
        TrafficVehicleType.CAR: "Xe ô tô",
        TrafficVehicleType.MOTORCYCLE: "Xe máy",
        TrafficVehicleType.BICYCLE: "Xe đạp",
        TrafficVehicleType.BUS: "Xe buýt",
        TrafficVehicleType.TRUCK: "Xe tải",
        TrafficVehicleType.CONTAINER: "Xe Container",
        TrafficVehicleType.SPECIAL: "Xe ưu tiên",
        TrafficVehicleType.UNKNOWN: "Chưa rõ"
    }

    @classmethod
    def get_name(cls, vehicle_type: TrafficVehicleType) -> str:
        return cls._UI_NAMES.get(vehicle_type, vehicle_type.name)