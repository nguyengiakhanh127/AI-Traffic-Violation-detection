# --- START OF FILE gui/features/config_builder/managers/workspace_manager.py ---
from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
from gui.shared_components.event_broker import app_broker

import uuid
from PyQt6.QtCore import QRectF
from gui.features.config_builder.graphics_items.smart_shapes import NodeItem, EdgeItem, PolygonEntity, LineEntity, BboxEntity

class WorkspaceManager(QObject):
    """
    Quản lý bộ nhớ (Registry) của các đối tượng đồ họa đang được vẽ trên Canvas.
    Đồng thời điều phối các tín hiệu thao tác trên đồ họa.
    """
    def __init__(self, panel, canvas):
        super().__init__()
        self.panel = panel
        self.canvas = canvas

        self.drawn_objects = []
        self.active_drawing_card = None 
        self.active_drawing_role = None 
        
        # Ngân hàng dữ liệu đồ họa (Chuyển từ Controller sang)
        self.object_registry = {
            "POLYGONS": {},  
            "BBOXES": {},    
            "LINES": {},
            "RULES": {}      
        }

        self._wire_broker_signals()
        self._wire_canvas_signals()

    def _wire_broker_signals(self):
        """Lắng nghe các yêu cầu từ Event Broker (phát ra bởi các thẻ Config Card)"""
        app_broker.request_draw_polygon.connect(self.handle_draw_polygon_request)
        app_broker.request_draw_bbox.connect(self.handle_draw_bbox_request)
        app_broker.request_draw_line.connect(self.handle_draw_line_request)
        
        app_broker.request_highlight_polygon.connect(self.handle_highlight_on)
        app_broker.clear_highlight_polygon.connect(self.handle_highlight_off)
        
        app_broker.request_edge_count.connect(self.handle_edge_count_request)
        app_broker.request_highlight_sub_edge.connect(self.handle_sub_edge_highlight_on)
        app_broker.clear_highlight_sub_edge.connect(self.handle_sub_edge_highlight_off)
        
        app_broker.rule_updated.connect(self.handle_rule_update)

        app_broker.request_delete_entity.connect(self.handle_delete_entity_request)

        app_broker.request_toggle_rois_visibility.connect(self.handle_toggle_rois_visibility)

    def _wire_canvas_signals(self):
        """Lắng nghe tín hiệu khi Canvas vẽ xong hoặc xóa đồ họa"""
        self.canvas.polygon_completed.connect(self.handle_new_polygon)
        self.canvas.bbox_completed.connect(self.handle_new_bbox)
        self.canvas.line_completed.connect(self.handle_new_line)

    def broadcast_registry(self):
        """Bắn tín hiệu cập nhật danh sách ID xuống Panel"""
        registry_data = {
            "POLYGONS": list(self.object_registry["POLYGONS"].keys()),
            "BBOXES": list(self.object_registry["BBOXES"].keys()),
            "LINES": list(self.object_registry["LINES"].keys()),
            "RULES": list(self.object_registry["RULES"].keys())
        }
        self.panel.broadcast_registry_update(registry_data)

    @pyqtSlot()
    def reset_workspace(self):
        """Dọn dẹp toàn bộ dữ liệu an toàn"""
        reply = QMessageBox.question(
            self.canvas, 'Xác nhận', 
            'Làm mới toàn bộ không gian làm việc?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.drawn_objects.clear()
            
            # [VÁ LỖI]: Ép Canvas hủy bỏ hoàn toàn trạng thái vẽ hiện tại của Tool
            self.canvas._cancel_drawing()
            if self.canvas.active_tool:
                self.canvas.set_mode("NONE")
            
            self.canvas.scene.clear()
            self.canvas.image_item = None 
            self.canvas.viewport().update() 
            
            self.canvas.all_nodes.clear()
            self.object_registry = {"POLYGONS": {}, "BBOXES": {}, "LINES": {}, "RULES": {}}
            
            if hasattr(self.panel, 'reset_form'):
                self.panel.reset_form()
                
            self.broadcast_registry()
            return True
        return False

    # =========================================================
    # CÁC HÀM XỬ LÝ VẼ VÀ ĐỒ HỌA (Di dời từ Controller sang)
    # =========================================================

    @pyqtSlot(object)
    def handle_draw_polygon_request(self, requester_widget):
        self.active_drawing_card = requester_widget
        self.canvas.set_mode("DRAW_POLYGON")

    @pyqtSlot(object)
    def handle_draw_bbox_request(self, requester_widget):
        self.active_drawing_card = requester_widget
        self.canvas.set_mode("DRAW_BBOX")

    @pyqtSlot(object, str)
    def handle_draw_line_request(self, requester_widget, role: str):
        self.active_drawing_card = requester_widget
        self.active_drawing_role = role 
        self.canvas.set_mode("DRAW_LINE")

    @pyqtSlot(tuple)
    def handle_new_polygon(self, data_tuple):
        entity_id, poly_entity = data_tuple
        self.object_registry["POLYGONS"][entity_id] = poly_entity
        self.broadcast_registry()
        
        # [CẬP NHẬT]: Ép Thẻ (Lane/Zone) Link vào ID này
        if self.active_drawing_card is not None:
            # Gán thẳng ID vào combo_ref
            self.active_drawing_card.current_obj_id = entity_id
            
            # Ép ComboBox hiển thị ID này (Bắt buộc phải set bằng code vì ta đã tắt auto-select ở bước 1)
            idx = self.active_drawing_card.combo_ref.findText(entity_id)
            if idx >= 0: 
                self.active_drawing_card.combo_ref.setCurrentIndex(idx)
                
            # Render sub-edges
            self.handle_edge_count_request(self.active_drawing_card, entity_id)
            self.active_drawing_card = None 

    @pyqtSlot(tuple)
    def handle_new_bbox(self, data_tuple):
        entity_id, bbox_entity = data_tuple
        self.object_registry["BBOXES"][entity_id] = bbox_entity
        self.broadcast_registry()
        
        # [CẬP NHẬT]
        if self.active_drawing_card is not None:
            self.active_drawing_card.update_bbox_data(entity_id)
            self.active_drawing_card = None

    @pyqtSlot(tuple)
    def handle_new_line(self, data_tuple):
        entity_id, line_entity = data_tuple
        self.object_registry["LINES"][entity_id] = line_entity
        self.broadcast_registry() # Vẫn báo cho mọi người biết để có ID trong danh sách
        
        # [CẬP NHẬT]: Ép duy nhất cái Thẻ (Card) vừa yêu cầu vẽ phải Link vào ID này
        if self.active_drawing_card is not None and self.active_drawing_role is not None:
            # Gọi thẳng hàm của LightConfigWidget
            self.active_drawing_card.update_edges_data(self.active_drawing_role, entity_id)
            
            # Xóa dấu vết yêu cầu
            self.active_drawing_card = None
            self.active_drawing_role = None

    @pyqtSlot(str)
    def handle_highlight_on(self, entity_id: str):
        for category in self.object_registry.values():
            if entity_id in category:
                category[entity_id].set_highlight(True)
                break

    @pyqtSlot()
    def handle_highlight_off(self):
        for category in self.object_registry.values():
            for entity in category.values():
                if hasattr(entity, 'set_highlight'):
                    entity.set_highlight(False)

    @pyqtSlot(object, str)
    def handle_edge_count_request(self, requester_widget, entity_id: str):
        if entity_id in self.object_registry["POLYGONS"]:
            poly_entity = self.object_registry["POLYGONS"][entity_id]
            edge_count = len(poly_entity.edges)
            requester_widget.build_sub_edges_ui(edge_count)

    @pyqtSlot(str, int)
    def handle_sub_edge_highlight_on(self, entity_id: str, edge_index: int):
        if entity_id in self.object_registry["POLYGONS"]:
            self.object_registry["POLYGONS"][entity_id].highlight_sub_edge(edge_index, True)

    @pyqtSlot(str, int)
    def handle_sub_edge_highlight_off(self, entity_id: str, edge_index: int):
        if entity_id in self.object_registry["POLYGONS"]:
            self.object_registry["POLYGONS"][entity_id].highlight_sub_edge(edge_index, False)

    @pyqtSlot(object, str, str, set)
    def handle_rule_update(self, requester_card, old_id: str, new_id: str, allowed_vehicles: set):
        if old_id and old_id in self.object_registry["RULES"]:
            del self.object_registry["RULES"][old_id]
            
        if new_id:
            self.object_registry["RULES"][new_id] = allowed_vehicles
            
        self.broadcast_registry()
    
    @pyqtSlot(str)
    def handle_delete_entity_request(self, entity_id: str):
        """Tiêu diệt đối tượng đồ họa an toàn, bảo vệ các Đỉnh dùng chung (Shared Nodes)"""
        for category, obj_dict in self.object_registry.items():
            if entity_id in obj_dict:
                entity = obj_dict[entity_id]
                
                if category == "POLYGONS":
                    for edge in entity.edges:
                        edge.start_node.remove_edge(edge)
                        edge.end_node.remove_edge(edge)
                        if edge.scene() == self.canvas.scene:
                            self.canvas.scene.removeItem(edge)
                        
                    for node in entity.nodes:
                        if len(node.connected_edges) == 0:
                            if node in self.canvas.all_nodes: 
                                self.canvas.all_nodes.remove(node)
                            # [VÁ LỖI]: Kiểm tra xem node có thực sự nằm trên scene không trước khi xóa
                            if node.scene() == self.canvas.scene:
                                self.canvas.scene.removeItem(node)
                            
                    if entity.scene() == self.canvas.scene:
                        self.canvas.scene.removeItem(entity)

                elif category == "LINES":
                    entity.start_node.remove_edge(entity)
                    entity.end_node.remove_edge(entity)
                    
                    if entity.scene() == self.canvas.scene:
                        self.canvas.scene.removeItem(entity)
                    
                    for node in [entity.start_node, entity.end_node]:
                        if len(node.connected_edges) == 0:
                            if node in self.canvas.all_nodes: 
                                self.canvas.all_nodes.remove(node)
                            if node.scene() == self.canvas.scene:
                                self.canvas.scene.removeItem(node)

                elif category == "BBOXES":
                    if entity.scene() == self.canvas.scene:
                        self.canvas.scene.removeItem(entity)

                del obj_dict[entity_id]
                self.broadcast_registry()
                break

    @pyqtSlot(bool)
    def handle_toggle_rois_visibility(self, is_visible: bool):
        # Duyệt qua các ngân hàng đồ họa (Loại trừ "RULES")
        for category in ["POLYGONS", "BBOXES", "LINES"]:
            for entity in self.object_registry[category].values():
                
                # 1. Ẩn/hiện đối tượng gốc (Mảng màu Polygon, Box, v.v.)
                if hasattr(entity, 'setVisible'):
                    entity.setVisible(is_visible)
                
                # 2. [VÁ LỖI]: Ép ẩn/hiện Đích danh các CẠNH của Polygon
                if category == "POLYGONS" and hasattr(entity, 'edges'):
                    for edge in entity.edges:
                        if hasattr(edge, 'setVisible'):
                            edge.setVisible(is_visible)

        # 3. Ẩn/hiện các Đỉnh (Nodes) dùng chung của Polygon và Line
        for node in self.canvas.all_nodes:
            if hasattr(node, 'setVisible'):
                node.setVisible(is_visible)
    
    def silent_clear(self):
        """Xóa sạch đồ họa và registry nhưng KHÔNG xóa nền Video (image_item)"""
        # Gọi hàm xóa thực thể chuẩn để dọn dẹp sạch sẽ
        for category in self.object_registry.values():
            for entity_id in list(category.keys()):
                self.handle_delete_entity_request(entity_id)
                
        self.object_registry = {"POLYGONS": {}, "BBOXES": {}, "LINES": {}, "RULES": {}}
        self.canvas.all_nodes.clear()

    def decompile_graphics(self, json_data: dict):
        """Dịch ngược tọa độ JSON thành Đồ họa Vector trên Canvas"""
        self.silent_clear()

        # 1. TÁI TẠO ĐA GIÁC (Lanes & Zones)
        for item in json_data.get("lanes", []) + json_data.get("zones", []):
            poly_id = f"OBJ_{str(uuid.uuid4())[:8].upper()}"
            nodes, edges = [], []
            
            # Lấy tọa độ (Lane dùng 'edges', Zone dùng 'vertices')
            points = [e["p1"] for e in item.get("edges", [])] if "edges" in item else item.get("vertices", [])
            if not points: continue

            # Sinh Đỉnh (Nodes)
            for pt in points:
                node = NodeItem(pt[0], pt[1])
                self.canvas.scene.addItem(node)
                self.canvas.all_nodes.append(node)
                nodes.append(node)

            # Sinh Cạnh (Edges) nối vòng tròn
            for i in range(len(nodes)):
                n1, n2 = nodes[i], nodes[(i + 1) % len(nodes)]
                edge = EdgeItem(n1, n2)
                self.canvas.scene.addItem(edge)
                n1.add_edge(edge); n2.add_edge(edge)
                edges.append(edge)

            # Sinh Đa giác mẹ
            poly = PolygonEntity(nodes, edges, poly_id)
            self.canvas.scene.addItem(poly)
            for node in nodes: node.parent_polygon = poly
            
            self.object_registry["POLYGONS"][poly_id] = poly
            item["_mapped_poly_id"] = poly_id # Lưu ID tạm để lát UI Card móc vào

        # 2. TÁI TẠO ĐÈN GIAO THÔNG
        for light in json_data.get("traffic_lights", []):
            # Bbox
            b = light.get("bbox")
            if b and len(b) == 4:
                bbox_id = f"LIGHT_{str(uuid.uuid4())[:8].upper()}"
                
                # [VÁ LỖI TỌA ĐỘ]: Chuyển (x1, y1, x2, y2) từ JSON về lại (x, y, width, height)
                x = b[0]
                y = b[1]
                w = b[2] - b[0] # width = x2 - x1
                h = b[3] - b[1] # height = y2 - y1
                
                bbox_entity = BboxEntity(QRectF(x, y, w, h), bbox_id)
                self.canvas.scene.addItem(bbox_entity)
                self.object_registry["BBOXES"][bbox_id] = bbox_entity
                light["_mapped_bbox_id"] = bbox_id

            # Helper tạo Line
            def _create_line(data_pts, prefix="LINE"):
                if not data_pts: return None
                lid = f"{prefix}_{str(uuid.uuid4())[:8].upper()}"
                n1, n2 = NodeItem(data_pts["p1"][0], data_pts["p1"][1]), NodeItem(data_pts["p2"][0], data_pts["p2"][1])
                for n in [n1, n2]:
                    self.canvas.scene.addItem(n)
                    self.canvas.all_nodes.append(n)
                line = LineEntity(n1, n2, lid)
                self.canvas.scene.addItem(line)
                n1.add_edge(line); n2.add_edge(line)
                self.object_registry["LINES"][lid] = line
                return lid

            light["_mapped_stop_id"] = _create_line(light.get("stop_line"))
            light["_mapped_right_id"] = _create_line(light.get("right_turn_line"))

        # Phát sóng ID mới cho UI
        self.broadcast_registry()