from utils.enums import TrafficVehicleType
from ultralytics.utils import YAML 
from typing import Dict, List

class YAML_ClassMapper:
    def __init__(self, yaml_path: str):
        self.yaml_data: Dict[int, str] = YAML.load(yaml_path)['names']
        self.mapping_rules: Dict[TrafficVehicleType, List[str]] = {
            TrafficVehicleType.CAR: ['car', 'suv', 'sedan', 'van'],
            TrafficVehicleType.MOTORCYCLE: ['motorcycle', 'motorbike', 'scooter'],
            TrafficVehicleType.BICYCLE: ['bicycle'],
            TrafficVehicleType.BUS: ['bus'],
            TrafficVehicleType.TRUCK: ['truck'],
            TrafficVehicleType.CONTAINER: ['container_truck', 'trailer']
        }

    def get_vehicle_type(self, object_id: int) -> TrafficVehicleType:
        for vehicle_category, vehicle_name in self.mapping_rules.items():
            if self.yaml_data.get(int(object_id), "").lower() in vehicle_name:
                return vehicle_category
        return TrafficVehicleType.UNKNOWN