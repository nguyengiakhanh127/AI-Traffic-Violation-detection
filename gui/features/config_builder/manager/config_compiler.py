# --- START OF FILE gui/features/config_builder/manager/config_compiler.py ---

import logging
from PyQt6.QtWidgets import QMessageBox
from geometry.primitives import Vertex
from geometry.shapes import Edge, Polygon
from core.lane import TrafficLane, TrafficZone
from core.rules import TrafficLaneRule
from utils.enums import TrafficLineType, TrafficZoneType, TrafficVehicleType
from core.trafficlight import TrafficLight

from gui.features.config_builder.components.lane_config_widget import LaneConfigWidget
from gui.features.config_builder.components.zone_config_widget import ZoneConfigWidget
from gui.features.config_builder.components.light_config_widget import LightConfigWidget

logger = logging.getLogger("ConfigCompiler")

class ConfigCompiler:
    """
    Trình biên dịch: Quét qua các Widget cấu hình và dữ liệu đồ họa, 
    đóng gói thành các thực thể toán học cho AI (Lane, Zone, TrafficLight).
    """
    def __init__(self, panel, workspace_mgr, lane_manager, zone_manager, traffic_lights_list):
        self.panel = panel
        self.workspace_mgr = workspace_mgr
        self.lane_manager = lane_manager
        self.zone_manager = zone_manager
        self.traffic_lights_list = traffic_lights_list 

    def compile(self) -> bool:
        compiled_lanes = []
        compiled_zones = []
        compiled_lights = [] 
        
        layout = self.panel.object_list_layout
        
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if widget is None: 
                continue
                
            try:
                # -------------------------------------------------------------
                # DỊCH THẺ: LÀN ĐƯỜNG
                # -------------------------------------------------------------
                if isinstance(widget, LaneConfigWidget):
                    lane_id = widget.input_id.text().strip()
                    poly_id = widget.current_obj_id
                    
                    if not lane_id or not poly_id or poly_id not in self.workspace_mgr.object_registry["POLYGONS"]:
                        QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Làn đường số {i+1} chưa hoàn thiện dữ liệu!")
                        return False
                        
                    poly_entity = self.workspace_mgr.object_registry["POLYGONS"][poly_id]
                    core_edges = []
                    
                    for idx, graph_edge in enumerate(poly_entity.edges):
                        p1_pos = graph_edge.start_node.sceneBoundingRect().center()
                        p2_pos = graph_edge.end_node.sceneBoundingRect().center()
                        v1, v2 = Vertex(p1_pos.x(), p1_pos.y()), Vertex(p2_pos.x(), p2_pos.y())
                        
                        line_type_str = widget.sub_edge_combos[idx].currentText().upper()
                        # Xử lý fallback an toàn nếu UI trả về Tiếng Việt
                        if "LIỀN" in line_type_str: l_type = TrafficLineType.SOLID
                        elif "ĐỨT" in line_type_str: l_type = TrafficLineType.DASHED
                        elif "VÀO" in line_type_str: l_type = TrafficLineType.ENTRY
                        elif "RA" in line_type_str: l_type = TrafficLineType.EXIT
                        else:
                            try: l_type = TrafficLineType[line_type_str]
                            except KeyError: l_type = TrafficLineType.SOLID
                            
                        core_edges.append(Edge(v1, v2, l_type))
                        
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
                        QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Vùng cấm số {i+1} chưa hoàn thiện dữ liệu!")
                        return False
                        
                    poly_entity = self.workspace_mgr.object_registry["POLYGONS"][poly_id]
                    core_vertices = [Vertex(n.sceneBoundingRect().center().x(), n.sceneBoundingRect().center().y()) for n in poly_entity.nodes]
                    
                    try:
                        zone_type = TrafficZoneType[widget.combo_type.currentText().upper()]
                    except KeyError:
                        zone_type = TrafficZoneType.FORBIDDEN_AREA
                    
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
                # DỊCH THẺ: ĐÈN GIAO THÔNG
                # -------------------------------------------------------------
                elif isinstance(widget, LightConfigWidget):
                    light_id = widget.input_id.text().strip()
                    bbox_id = widget.current_bbox_id
                    stop_id = widget.current_stop_id
                    right_id = widget.current_right_id

                    if not light_id or not bbox_id or not stop_id:
                        QMessageBox.warning(self.panel, "Lỗi Biên dịch", f"Đèn giao thông số {i+1} bị thiếu liên kết đồ họa!")
                        return False
                        
                    if bbox_id not in self.workspace_mgr.object_registry["BBOXES"]:
                        return False
                    if stop_id not in self.workspace_mgr.object_registry["LINES"]:
                        return False

                    bbox_entity = self.workspace_mgr.object_registry["BBOXES"][bbox_id]
                    rect = bbox_entity.rect()
                    core_bbox = (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))

                    stop_line_entity = self.workspace_mgr.object_registry["LINES"][stop_id]
                    sp1 = stop_line_entity.start_node.sceneBoundingRect().center()
                    sp2 = stop_line_entity.end_node.sceneBoundingRect().center()
                    # [VÁ LỖI]: Dùng SOLID thay vì VIRTUAL không tồn tại
                    core_stop_line = Edge(Vertex(sp1.x(), sp1.y()), Vertex(sp2.x(), sp2.y()), TrafficLineType.SOLID)

                    core_right_line = None
                    if right_id and right_id in self.workspace_mgr.object_registry["LINES"]:
                        rp_entity = self.workspace_mgr.object_registry["LINES"][right_id]
                        rp1 = rp_entity.start_node.sceneBoundingRect().center()
                        rp2 = rp_entity.end_node.sceneBoundingRect().center()
                        core_right_line = Edge(Vertex(rp1.x(), rp1.y()), Vertex(rp2.x(), rp2.y()), TrafficLineType.DASHED)

                    compiled_lights.append(TrafficLight(
                        light_id=light_id,
                        bbox_rect=core_bbox,
                        stop_line=core_stop_line,
                        right_turn_line=core_right_line
                    ))
                    
            except Exception as e:
                logger.error(f"Lỗi biên dịch thẻ thứ {i+1}: {e}")
                QMessageBox.critical(self.panel, "Lỗi Nghiêm Trọng", f"Xảy ra lỗi khi biên dịch thẻ {i+1}.\nVui lòng kiểm tra lại dữ liệu nhập.")
                return False

        # Đẩy xuống Core
        self.lane_manager.lanes = compiled_lanes
        self.zone_manager.zones = compiled_zones
        
        self.traffic_lights_list.clear()
        self.traffic_lights_list.extend(compiled_lights)
        
        logger.info(f"Dịch thành công {len(compiled_lanes)} Làn, {len(compiled_zones)} Vùng cấm, {len(compiled_lights)} Đèn giao thông.")
        return True

# --- END OF FILE gui/features/config_builder/manager/config_compiler.py ---