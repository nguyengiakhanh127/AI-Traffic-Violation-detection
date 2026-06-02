# --- START OF FILE gui/features/config_builder/managers/config_compiler.py ---
from PyQt6.QtWidgets import QMessageBox
from geometry.primitives import Vertex
from geometry.shapes import Edge, Polygon
from core.lane import TrafficLane, TrafficZone
from core.rules import TrafficLaneRule
from utils.enums import TrafficLineType, TrafficZoneType, TrafficVehicleType

from gui.features.config_builder.components.lane_config_widget import LaneConfigWidget
from gui.features.config_builder.components.zone_config_widget import ZoneConfigWidget

class ConfigCompiler:
    """
    Trình biên dịch: Chuyên trách quét qua giao diện người dùng (Panel), 
    kết hợp với dữ liệu tọa độ đồ họa (WorkspaceManager) để đóng gói thành 
    các thực thể AI lõi (Core Entities) cho hệ thống giám sát.
    """
    def __init__(self, panel, workspace_mgr, lane_manager, zone_manager):
        self.panel = panel
        self.workspace_mgr = workspace_mgr
        self.lane_manager = lane_manager
        self.zone_manager = zone_manager

    def compile(self) -> bool:
        """Thực thi biên dịch. Trả về True nếu thành công, False nếu có lỗi dữ liệu."""
        compiled_lanes = []
        compiled_zones = []
        
        layout = self.panel.object_list_layout
        
        # Duyệt qua từng thẻ cấu hình có trên giao diện
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget is None: 
                continue
                
            # -------------------------------------------------------------
            # DỊCH THẺ: LÀN ĐƯỜNG
            # -------------------------------------------------------------
            if isinstance(widget, LaneConfigWidget):
                lane_id = widget.input_id.text().strip()
                poly_id = widget.current_obj_id
                
                # Kiểm tra tính hợp lệ
                if not lane_id or not poly_id or poly_id not in self.workspace_mgr.object_registry["POLYGONS"]:
                    QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Làn đường ở vị trí số {i+1} chưa điền ID hoặc chưa liên kết tọa độ đồ họa!")
                    return False
                    
                poly_entity = self.workspace_mgr.object_registry["POLYGONS"][poly_id]
                core_edges = []
                
                # Dịch các đoạn thẳng đồ họa sang Edge toán học
                for idx, graph_edge in enumerate(poly_entity.edges):
                    p1_pos = graph_edge.start_node.sceneBoundingRect().center()
                    p2_pos = graph_edge.end_node.sceneBoundingRect().center()
                    v1, v2 = Vertex(p1_pos.x(), p1_pos.y()), Vertex(p2_pos.x(), p2_pos.y())
                    
                    line_type_str = widget.sub_edge_combos[idx].currentText()
                    core_edges.append(Edge(v1, v2, TrafficLineType[line_type_str]))
                    
                # Dịch Luật giao thông
                rule_id = widget.combo_rule_ref.currentText()
                if not rule_id or rule_id == "Trống":
                    allowed_vehicles = set(e for e in TrafficVehicleType if e != TrafficVehicleType.UNKNOWN)
                else:
                    allowed_vehicles = self.workspace_mgr.object_registry["RULES"].get(rule_id, set())
                    
                lane_rule = TrafficLaneRule(allowed_vehicles)
                compiled_lanes.append(TrafficLane(lane_id, core_edges, lane_rule))

            # -------------------------------------------------------------
            # DỊCH THẺ: VÙNG CẤM
            # -------------------------------------------------------------
            elif isinstance(widget, ZoneConfigWidget):
                zone_id = widget.input_id.text().strip()
                poly_id = widget.current_obj_id
                
                # Kiểm tra tính hợp lệ
                if not zone_id or not poly_id or poly_id not in self.workspace_mgr.object_registry["POLYGONS"]:
                    QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Vùng cấm ở vị trí số {i+1} chưa điền ID hoặc chưa liên kết tọa độ!")
                    return False
                    
                poly_entity = self.workspace_mgr.object_registry["POLYGONS"][poly_id]
                core_vertices = [Vertex(n.sceneBoundingRect().center().x(), n.sceneBoundingRect().center().y()) for n in poly_entity.nodes]
                
                zone_type = TrafficZoneType[widget.combo_type.currentText()]
                
                days_text = widget.combo_days.currentText()
                prohibited_days = None
                if "EVEN" in days_text or "chẵn" in days_text.lower(): prohibited_days = "EVEN"
                elif "ODD" in days_text or "lẻ" in days_text.lower(): prohibited_days = "ODD"

                compiled_zones.append(TrafficZone(
                    zone_id=zone_id, 
                    zone_type=zone_type, 
                    polygon=Polygon(core_vertices),
                    prohibited_hours=(widget.spin_start_hour.value(), widget.spin_end_hour.value()),
                    prohibited_days=prohibited_days
                ))
                
            # TODO: DỊCH THẺ ĐÈN GIAO THÔNG (Sẽ thêm vào khi làm tính năng Đèn đỏ)

        # Cập nhật kết quả vào bộ nhớ hệ thống lõi (Core)
        self.lane_manager.lanes = compiled_lanes
        self.zone_manager.zones = compiled_zones
        print(f"[COMPILER]: Dịch thành công {len(compiled_lanes)} Làn đường và {len(compiled_zones)} Vùng cấm.")
        return True

# --- END OF FILE gui/features/config_builder/managers/config_compiler.py ---