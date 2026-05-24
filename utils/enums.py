from enum import Enum, auto

class TrafficVehicleType(Enum):
    BICYCLE = auto()
    MOTORCYCLE = auto()
    CAR = auto()         
    BUS = auto()         
    TRUCK = auto()       
    CONTAINER = auto()   
    SPECIAL = auto()     
    UNKNOWN = auto()

class TrafficLineType(Enum):
    SOLID = "Solid"     
    DASHED = "Dashed"   
    VIRTUAL = "Virtual"

class ViolationType(Enum):
    WRONG_LANE = auto()                 # Đi sai làn đường
    LINE_CROSSING = auto()              # Đè vạch phân làn
    WRONG_WAY = auto()                  # Đi ngược chiều
    FORBIDDEN_ENTRY = auto()            # Đi vào đường cấm
    ILLEGAL_PARKING = auto()            # Dừng đỗ xe trái quy định
    PEDESTRIAN_CROSSING_STOP = auto()   # Dừng xe đè vạch người đi bộ

class TrafficZoneType(Enum):
    PEDESTRIAN_CROSSING = auto()        # Vạch kẻ đi bộ
    NO_PARKING = auto()                 # Vùng cấm đỗ xe
    FORBIDDEN_AREA = auto()             # Vùng cấm đi vào

# --- END OF FILE enums.py ---