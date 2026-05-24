from typing import Set, Dict
from utils.enums import TrafficVehicleType,  ViolationType

class TrafficLaneRule:
    def __init__(self, allowed_vehicles: Set['TrafficVehicleType']):
        self.allowed_vehicles = allowed_vehicles

    def is_allowed(self, vehicle_type: 'TrafficVehicleType') -> bool:
        return vehicle_type in self.allowed_vehicles

class ViolationRegistry:
    _METADATA: Dict[ViolationType, Dict[str, str]] = {
        
        ViolationType.WRONG_LANE: {
            "code": "DI_SAI_LAN",
            "desc": "Đi không đúng làn đường quy định cho từng loại phương tiện"
        },
        ViolationType.LINE_CROSSING: {
            "code": "DE_VACH_PHAN_LAN",
            "desc": "Không chấp hành hiệu lệnh, chỉ dẫn của vạch kẻ đường (đè vạch liền phân làn)"
        },
        ViolationType.WRONG_WAY: {
            "code": "DI_NGUOC_CHIEU",
            "desc": "Đi ngược chiều của đường một chiều hoặc đường có biển 'Cấm đi ngược chiều'"
        },
        ViolationType.FORBIDDEN_ENTRY: {
            "code": "VAO_DUONG_CAM",
            "desc": "Đi vào khu vực cấm, đường có biển báo hiệu có nội dung cấm đi vào"
        },
        ViolationType.ILLEGAL_PARKING: {
            "code": "DUNG_DO_TRAI_QUY_DINH",
            "desc": "Dừng xe, đỗ xe trái quy định của pháp luật đường bộ"
        },
        ViolationType.PEDESTRIAN_CROSSING_STOP: {
            "code": "DO_TREN_VACH_DI_BO",
            "desc": "Dừng xe, đỗ xe đè lên vạch kẻ đường dành cho người đi bộ"
        }
    }

    @classmethod
    def get_code(cls, violation_type: ViolationType) -> str:
        return cls._METADATA.get(violation_type, {}).get("code", "UNKNOWN")

    @classmethod
    def get_description(cls, violation_type: ViolationType) -> str:
        return cls._METADATA.get(violation_type, {}).get("desc", "Không xác định")