import json
import logging
from typing import Dict, List, Optional, Tuple, Set

from utils.enums import TrafficLineType, TrafficVehicleType, TrafficZoneType
from geometry.primitives import Vertex
from geometry.shapes import Edge, Polygon
from core.lane import TrafficLane, TrafficZone
from core.rules import TrafficLaneRule


logger = logging.getLogger("ConfigService")

class ConfigService:
    @staticmethod
    def load_configuration(filepath: str) -> Tuple[List[TrafficLane], List[TrafficZone], List[TrafficLight]]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            logger.info(f"Đang đọc cấu hình từ: {filepath}")
            
            lanes = ConfigService._parse_lanes(data.get("lanes", []))
            zones = ConfigService._parse_zones(data.get("zones", []))
            lights = ConfigService._parse_traffic_lights(data.get("traffic_lights", []))
            
            logger.info(f"✅ Tải cấu hình thành công: {len(lanes)} Làn, {len(zones)} Vùng cấm, {len(lights)} Đèn giao thông.")
            return lanes, zones, lights
            
        except FileNotFoundError:
            logger.error(f"❌ Không tìm thấy tệp cấu hình tại: {filepath}")
            return [], [], []
        except json.JSONDecodeError:
            logger.error(f"❌ Tệp cấu hình JSON bị lỗi định dạng: {filepath}")
            return [], [], []
        except Exception as e:
            logger.error(f"❌ Lỗi hệ thống khi phân tích cấu hình: {e}")
            return [], [], []

    @staticmethod
    def _parse_vertex(data: List[float]) -> Vertex:
        return Vertex(float(data[0]), float(data[1]))

    @staticmethod
    def _parse_edge(data: dict) -> Edge:
        p1 = ConfigService._parse_vertex(data["p1"])
        p2 = ConfigService._parse_vertex(data["p2"])
        
        line_type_str = data.get("type", "VIRTUAL").upper()
        line_type = TrafficLineType[line_type_str]
        
        return Edge(p1, p2, line_type)

    @staticmethod
    def _parse_lanes(lane_data: list) -> List[TrafficLane]:
        lanes = []
        for l_data in lane_data:
            lane_id = l_data.get("id", "Unknown_Lane")
            
            allowed_vehicles: Set[TrafficVehicleType] = set()
            for v_type_str in l_data.get("allowed_vehicles", []):
                try:
                    allowed_vehicles.add(TrafficVehicleType[v_type_str.upper()])
                except KeyError:
                    pass
            lane_rule = TrafficLaneRule(allowed_vehicles)
            
            edges = [ConfigService._parse_edge(e) for e in l_data.get("edges", [])]
            
            if edges:
                lanes.append(TrafficLane(lane_id, edges, lane_rule))
                
        return lanes

    @staticmethod
    def _parse_zones(zone_data: list) -> List[TrafficZone]:
        zones = []
        for z_data in zone_data:
            zone_id = z_data.get("id", "Unknown_Zone")
            
            zone_type_str = z_data.get("type", "FORBIDDEN_AREA").upper()
            zone_type = TrafficZoneType[zone_type_str]
            
            vertices = [ConfigService._parse_vertex(v) for v in z_data.get("vertices", [])]
            polygon = Polygon(vertices)
            
            prohibited_hours = z_data.get("prohibited_hours") # Ví dụ: [6, 22]
            prohibited_days = z_data.get("prohibited_days")   # Ví dụ: "EVEN" hoặc "ODD"
            
            p_hours_tuple = tuple(prohibited_hours) if prohibited_hours and len(prohibited_hours) == 2 else None
            
            zones.append(TrafficZone(
                zone_id=zone_id, 
                zone_type=zone_type, 
                polygon=polygon,
                prohibited_hours=p_hours_tuple,
                prohibited_days=prohibited_days
            ))
            
        return zones
