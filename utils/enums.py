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
    ENTRY = "Entry"     
    EXIT = "Exit"      

class ViolationType(Enum):
    WRONG_LANE = auto()                
    LINE_CROSSING = auto()          
    WRONG_WAY = auto()                
    FORBIDDEN_ENTRY = auto()            
    ILLEGAL_PARKING = auto()           
    PEDESTRIAN_CROSSING_STOP = auto()  
    RED_LINE = auto()

class TrafficZoneType(Enum):
    PEDESTRIAN_CROSSING = auto()     
    NO_PARKING = auto()               
    FORBIDDEN_AREA = auto()         

class TrafficLightColor(Enum):
    RED = auto()
    YELLOW = auto()
    GREEN = auto()
    OFF = auto()
