from PyQt6.QtWidgets import QMessageBox
from geometry.primitives import Vertex
from geometry.shapes import Edge, Polygon
from core.lane import TrafficLane, TrafficZone
from core.rules import TrafficLaneRule
from utils.enums import TrafficLineType, TrafficZoneType, TrafficVehicleType

# [THÊM MỚI 1]: Import TrafficLight từ Core
from core.trafficlight import TrafficLight

from gui.features.config_builder.components.lane_config_widget import LaneConfigWidget
from gui.features.config_builder.components.zone_config_widget import ZoneConfigWidget
# [THÊM MỚI 2]: Import LightConfigWidget
from gui.features.config_builder.components.light_config_widget import LightConfigWidget

class ConfigCompiler:
    """
    Trình biên dịch: Chuyên trách quét qua giao diện người dùng (Panel), 
    kết hợp với dữ liệu tọa độ đồ họa (WorkspaceManager) để đóng gói thành 
    các thực thể AI lõi (Core Entities) cho hệ thống giám sát.
    """
    def __init__(self, panel, workspace_mgr, lane_manager, zone_manager, traffic_lights_list):
        self.panel = panel
        self.workspace_mgr = workspace_mgr
        self.lane_manager = lane_manager
        self.zone_manager = zone_manager
        # [THÊM MỚI 3]: Nhận tham chiếu đến danh sách đèn của Controller
        self.traffic_lights_list = traffic_lights_list 

    def compile(self) -> bool:
        """Thực thi biên dịch. Trả về True nếu thành công, False nếu có lỗi dữ liệu."""
        compiled_lanes = []
        compiled_zones = []
        compiled_lights = [] # Chứa danh sách đèn tạm thời
        
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
                
                if not lane_id or not poly_id or poly_id not in self.workspace_mgr.object_registry["POLYGONS"]:
                    QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Làn đường ở vị trí số {i+1} chưa điền ID hoặc chưa liên kết tọa độ đồ họa!")
                    return False
                    
                poly_entity = self.workspace_mgr.object_registry["POLYGONS"][poly_id]
                core_edges = []
                
                for idx, graph_edge in enumerate(poly_entity.edges):
                    p1_pos = graph_edge.start_node.sceneBoundingRect().center()
                    p2_pos = graph_edge.end_node.sceneBoundingRect().center()
                    v1, v2 = Vertex(p1_pos.x(), p1_pos.y()), Vertex(p2_pos.x(), p2_pos.y())
                    
                    line_type_str = widget.sub_edge_combos[idx].currentText()
                    core_edges.append(Edge(v1, v2, TrafficLineType[line_type_str]))
                    
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
                
            # -------------------------------------------------------------
            # [THÊM MỚI]: DỊCH THẺ ĐÈN GIAO THÔNG
            # -------------------------------------------------------------
            elif isinstance(widget, LightConfigWidget):
                light_id = widget.input_id.text().strip()
                bbox_id = widget.current_bbox_id
                stop_id = widget.current_stop_id
                right_id = widget.current_right_id

                # 1. Rào chắn lỗi: Thiếu ID, thiếu Bbox hoặc thiếu Vạch dừng là không được
                if not light_id:
                    QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Đèn giao thông ở vị trí số {i+1} chưa điền ID!")
                    return False
                if not bbox_id or bbox_id not in self.workspace_mgr.object_registry["BBOXES"]:
                    QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Đèn '{light_id}' chưa liên kết vùng quét màu (BBox)!")
                    return False
                if not stop_id or stop_id not in self.workspace_mgr.object_registry["LINES"]:
                    QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Đèn '{light_id}' chưa liên kết Vạch dừng (Stop Line)!")
                    return False

                # 2. Dịch Bounding Box (Lấy tọa độ x, y, w, h từ đồ họa)
                bbox_entity = self.workspace_mgr.object_registry["BBOXES"][bbox_id]
                rect = bbox_entity.rect()
                core_bbox = (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))

                # 3. Dịch Vạch dừng (Stop Line)
                stop_line_entity = self.workspace_mgr.object_registry["LINES"][stop_id]
                sp1 = stop_line_entity.start_node.sceneBoundingRect().center()
                sp2 = stop_line_entity.end_node.sceneBoundingRect().center()
                core_stop_line = Edge(Vertex(sp1.x(), sp1.y()), Vertex(sp2.x(), sp2.y()), TrafficLineType.VIRTUAL)

                # 4. Dịch Vạch rẽ phải (Tùy chọn - Có thể không có)
                core_right_line = None
                if right_id and right_id in self.workspace_mgr.object_registry["LINES"]:
                    rp_entity = self.workspace_mgr.object_registry["LINES"][right_id]
                    rp1 = rp_entity.start_node.sceneBoundingRect().center()
                    rp2 = rp_entity.end_node.sceneBoundingRect().center()
                    core_right_line = Edge(Vertex(rp1.x(), rp1.y()), Vertex(rp2.x(), rp2.y()), TrafficLineType.VIRTUAL)

                # 5. Khởi tạo đối tượng TrafficLight
                compiled_lights.append(TrafficLight(
                    light_id=light_id,
                    bbox_rect=core_bbox,
                    stop_line=core_stop_line,
                    right_turn_line=core_right_line
                ))

        # Cập nhật kết quả vào bộ nhớ hệ thống lõi (Core)
        self.lane_manager.lanes = compiled_lanes
        self.zone_manager.zones = compiled_zones
        
        # [THÊM MỚI]: Cập nhật danh sách đèn bằng cách clear() rồi extend() để giữ tham chiếu (pointer)
        self.traffic_lights_list.clear()
        self.traffic_lights_list.extend(compiled_lights)
        
        print(f"[COMPILER]: Dịch thành công {len(compiled_lanes)} Làn, {len(compiled_zones)} Vùng cấm, {len(compiled_lights)} Đèn giao thông.")
        return True