# --- START OF FILE services/config_service.py ---

import json
import logging
from typing import Dict, List, Optional, Tuple, Set, Any

from utils.enums import TrafficLineType, TrafficVehicleType, TrafficZoneType
from geometry.primitives import Vertex
from geometry.shapes import Edge, Polygon
from core.lane import TrafficLane, TrafficZone
from core.rules import TrafficLaneRule
from core.trafficlight import TrafficLight

logger = logging.getLogger("ConfigService")

class ConfigService:
    """
    Dịch vụ nạp cấu hình không gian (Làn đường, Vùng cấm, Đèn giao thông).
    Đã được chuyển sang dạng Instance để hỗ trợ Dependency Injection sau này.
    """
    def load_configuration(self, filepath: str) -> Tuple[List[TrafficLane], List[TrafficZone], List[TrafficLight]]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            logger.info(f"Đang đọc cấu hình từ: {filepath}")
            
            lanes = self._parse_lanes(data.get("lanes", []))
            zones = self._parse_zones(data.get("zones", []))
            lights = self._parse_traffic_lights(data.get("traffic_lights", []))
            
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

    def _parse_vertex(self, data: List[float]) -> Vertex:
        return Vertex(float(data[0]), float(data[1]))

    def _parse_edge(self, data: dict) -> Edge:
        p1 = self._parse_vertex(data["p1"])
        p2 = self._parse_vertex(data["p2"])
        
        line_type_str = data.get("type", "VIRTUAL").upper()
        line_type = TrafficLineType[line_type_str]
        
        return Edge(p1, p2, line_type)

    def _parse_lanes(self, lane_data: list) -> List[TrafficLane]:
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
            
            edges = [self._parse_edge(e) for e in l_data.get("edges", [])]
            if edges:
                lanes.append(TrafficLane(lane_id, edges, lane_rule))
        return lanes

    def _parse_zones(self, zone_data: list) -> List[TrafficZone]:
        zones = []
        for z_data in zone_data:
            zone_id = z_data.get("id", "Unknown_Zone")
            
            zone_type_str = z_data.get("type", "FORBIDDEN_AREA").upper()
            zone_type = TrafficZoneType[zone_type_str]
            
            vertices = [self._parse_vertex(v) for v in z_data.get("vertices", [])]
            polygon = Polygon(vertices)
            
            prohibited_hours = z_data.get("prohibited_hours")
            prohibited_days = z_data.get("prohibited_days")
            
            p_hours_tuple = tuple(prohibited_hours) if prohibited_hours and len(prohibited_hours) == 2 else None
            
            zones.append(TrafficZone(
                zone_id=zone_id, 
                zone_type=zone_type, 
                polygon=polygon,
                prohibited_hours=p_hours_tuple,
                prohibited_days=prohibited_days
            ))
        return zones

    def _parse_traffic_lights(self, light_data: list) -> List[TrafficLight]:
        """[VÁ LỖI]: Bổ sung hàm parse dữ liệu đèn giao thông"""
        lights = []
        for l_data in light_data:
            try:
                light_id = l_data.get("id", "Unknown_Light")
                bbox = l_data.get("bbox", [0, 0, 10, 10]) # [x, y, w, h]
                bbox_tuple = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
                
                stop_line_data = l_data.get("stop_line")
                if not stop_line_data:
                    continue # Đèn bắt buộc phải có vạch dừng
                stop_line = self._parse_edge(stop_line_data)
                
                right_turn_data = l_data.get("right_turn_line")
                right_turn_line = self._parse_edge(right_turn_data) if right_turn_data else None
                
                lights.append(TrafficLight(
                    light_id=light_id,
                    bbox_rect=bbox_tuple,
                    stop_line=stop_line,
                    right_turn_line=right_turn_line
                ))
            except Exception as e:
                logger.error(f"Lỗi parse đèn giao thông {l_data.get('id')}: {e}")
        return lights

# --- END OF FILE services/config_service.py ---