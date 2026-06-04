# --- START OF FILE gui/features/config_builder/managers/workspace_manager.py ---
from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
from gui.shared_components.event_broker import app_broker

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
        """Dọn dẹp toàn bộ dữ liệu vẽ tay và trả Canvas về trạng thái chờ"""
        reply = QMessageBox.question(
            self.canvas, 'Xác nhận', 
            'Bạn có chắc chắn muốn làm mới toàn bộ không gian làm việc?\n(Bao gồm cả ảnh/video và các thẻ cấu hình)',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # 1. Xóa rác đồ họa
            self.drawn_objects.clear()
            self.canvas._cancel_drawing()
            
            # 2. XÓA TOÀN BỘ CÁC ITEM TRÊN SCENE (Bao gồm cả ảnh nền)
            self.canvas.scene.clear()
            self.canvas.image_item = None # [QUAN TRỌNG]: Gán bằng None để Canvas bật lại drawForeground
            self.canvas.viewport().update() # Ép Canvas vẽ lại ngay lập tức
            
            # 3. Xóa sổ sách
            self.canvas.all_nodes.clear()
            self.object_registry = {"POLYGONS": {}, "BBOXES": {}, "LINES": {}, "RULES": {}}
            
            # 4. Xóa UI bên phải (Right Panel)
            if hasattr(self.panel, 'reset_form'):
                self.panel.reset_form()
                
            self.broadcast_registry()
            
            # Bắn tín hiệu trả về True để Controller biết mà tắt Video (nếu đang chạy)
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
                
                # 1. XÓA ĐA GIÁC (An toàn tuyệt đối)
                if category == "POLYGONS":
                    # Bước A: Tháo gỡ và xóa tất cả các CẠNH của Đa giác này
                    for edge in entity.edges:
                        # Rút cạnh này ra khỏi danh sách kết nối của 2 đỉnh đầu mút của nó
                        edge.start_node.remove_edge(edge)
                        edge.end_node.remove_edge(edge)
                        # Rút khỏi màn hình
                        self.canvas.scene.removeItem(edge)
                        
                    # Bước B: Phán xét sự sống chết của các ĐỈNH
                    for node in entity.nodes:
                        # Nếu Đỉnh này không còn kết nối với Cạnh nào khác (không ai dùng chung)
                        if len(node.connected_edges) == 0:
                            self.canvas.scene.removeItem(node)
                            if node in self.canvas.all_nodes: 
                                self.canvas.all_nodes.remove(node)
                        else:
                            # Đỉnh này đang được Đa giác khác dùng chung -> ĐỂ YÊN ĐÓ!
                            pass 
                            
                    # Bước C: Xóa lớp màng màu (Fill)
                    self.canvas.scene.removeItem(entity)

                # 2. XÓA ĐƯỜNG THẲNG (Cũng dùng chung logic bảo vệ Đỉnh)
                elif category == "LINES":
                    entity.start_node.remove_edge(entity)
                    entity.end_node.remove_edge(entity)
                    
                    self.canvas.scene.removeItem(entity)
                    
                    for node in [entity.start_node, entity.end_node]:
                        if len(node.connected_edges) == 0:
                            self.canvas.scene.removeItem(node)
                            if node in self.canvas.all_nodes: 
                                self.canvas.all_nodes.remove(node)

                # 3. XÓA HỘP BBOX
                elif category == "BBOXES":
                    self.canvas.scene.removeItem(entity)

                # 4. Xóa sổ sách
                del obj_dict[entity_id]
                self.broadcast_registry()
                break