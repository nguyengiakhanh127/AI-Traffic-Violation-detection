from enum import Enum, auto

class TrafficVehicleType(Enum):
    BICYCLE = "Xe đạp"
    MOTORCYCLE = "Xe máy"
    CAR = "Ô tô con"         
    BUS = "Xe buýt"         
    TRUCK = "Xe tải"       
    CONTAINER = "Xe Container"   
    SPECIAL = "Xe ưu tiên"     
    UNKNOWN = "Không xác định"

class TrafficLineType(Enum):
    SOLID = "Nét liền"      
    DASHED = "Nét đứt"      
    ENTRY = "Hướng vào"    
    EXIT = "Hướng ra"       
    BOUNDARY = "Biên làn"    

class ViolationType(Enum):
    WRONG_LANE = auto()                
    LINE_CROSSING = auto()          
    WRONG_WAY = auto()                
    FORBIDDEN_ENTRY = auto()            
    ILLEGAL_PARKING = auto()           
    PEDESTRIAN_CROSSING_STOP = auto()  
    RED_LINE = auto()

class TrafficZoneType(Enum):
    PEDESTRIAN_CROSSING = "Vạch đi bộ"     
    NO_PARKING = "Vùng cấm dừng đỗ"               
    FORBIDDEN_AREA = "Khu vực cấm đi vào"

class TrafficLightColor(Enum):
    RED = auto()
    YELLOW = auto()
    GREEN = auto()
    OFF = auto()
