from PyQt6.QtWidgets import QGraphicsScene
from gui.features.config_builder.graphics_items.vehicle_visuals import VehicleVisualGroup
from utils.enums import TrafficVehicleType

class AIOverlayManager:
    """Chuyên quản lý lớp đồ họa đè lên video (Bounding Boxes, Trails của AI)"""
    def __init__(self, scene: QGraphicsScene):
        self.scene = scene
        self.visual_vehicles = {}
        self.visual_filters = {
            "show_cars": True, "show_motorcycles": True,
            "show_violators_only": False, "show_trails": True
        }

    def sync_ai_visuals(self, vehicles_list: list):
        seen_ids = set()
        
        for vehicle in vehicles_list:
            v_id = vehicle.id
            seen_ids.add(v_id)
            
            if v_id not in self.visual_vehicles:
                self.visual_vehicles[v_id] = VehicleVisualGroup(self.scene, v_id, vehicle.vehicle_type)
                
            visual_group = self.visual_vehicles[v_id]
            
            is_violating = len(vehicle.active_violations) > 0
            is_pending = len(getattr(vehicle, 'pending_violations', set())) > 0
            trajectory = list(vehicle.coordinate.trajectory) # Cập nhật lấy từ deque
            
            visual_group.update_state(
                bbox=vehicle.current_bbox, trajectory=trajectory,
                is_violating=is_violating, is_pending=is_pending,
                show_trail=self.visual_filters["show_trails"]
            )
            
            # Lọc hiển thị
            is_visible = True
            v_type = vehicle.vehicle_type
            if v_type in [TrafficVehicleType.CAR, TrafficVehicleType.TRUCK, TrafficVehicleType.BUS] and not self.visual_filters["show_cars"]:
                is_visible = False
            elif v_type == TrafficVehicleType.MOTORCYCLE and not self.visual_filters["show_motorcycles"]:
                is_visible = False
                
            if self.visual_filters["show_violators_only"] and not (is_violating or is_pending):
                is_visible = False
                
            visual_group.set_visible(is_visible)

        # Xóa xe mất dấu
        for vid in list(self.visual_vehicles.keys()):
            if vid not in seen_ids:
                self.visual_vehicles[vid].remove_from_scene()
                del self.visual_vehicles[vid]

    def clear_all(self):
        for v_group in list(self.visual_vehicles.values()):
            v_group.remove_from_scene()
        self.visual_vehicles.clear()