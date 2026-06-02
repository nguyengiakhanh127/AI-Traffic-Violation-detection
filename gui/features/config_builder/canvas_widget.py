import os
import math
import uuid
import numpy as np
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,  QGraphicsRectItem,  QGraphicsLineItem
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap, QPainter, QWheelEvent, QMouseEvent, QCursor, QTransform, QImage, QPen, QColor,  QBrush

# [CẬP NHẬT]: Import các "Diễn viên" từ thư mục mới
from gui.features.config_builder.graphics_items.smart_shapes import (
    PolygonEntity, EdgeItem, NodeItem, BboxEntity, LineEntity
)
from gui.features.config_builder.graphics_items.vehicle_visuals import VehicleVisualGroup

from typing import Dict

class ConfigCanvas(QGraphicsView):

    zoom_level_changed = pyqtSignal(int)
    polygon_completed = pyqtSignal(tuple) 
    bbox_completed = pyqtSignal(tuple)
    line_completed = pyqtSignal(tuple)

    item_deleted = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setBackgroundBrush(QBrush(QColor(20, 20, 22))) 

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        self.image_item: QGraphicsPixmapItem = None
        self.current_mode = "NONE"
        self.current_zoom = 100
        
        self.cursor_dir = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "cursors")

        # Quản lý hình học
        self.all_nodes = []           # Chứa TẤT CẢ các NodeItem trên màn hình (để phục vụ nam châm hút dính)
        self.current_drawing_nodes = [] # Các node đang thuộc cái hình vẽ dở dang
        self.current_drawing_edges = [] 
        self.ghost_line: QGraphicsLineItem = None 
        
        self.drawing_bbox: QGraphicsRectItem = None
        self.bbox_start_pos = None
        self.line_start_pos = None
        self.line_start_node = None

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        self.snapped_node = None # Biến lưu Node đang được nam châm hút trúng
        
        self.visual_vehicles: Dict[int, VehicleVisualGroup] = {}
        self.visual_filters = {
            "show_cars": True,
            "show_motorcycles": True,
            "show_violators_only": False,
            "show_trails": True
        }
    
    def drawForeground(self, painter: QPainter, rect):
        super().drawForeground(painter, rect)
        
        # Nếu đã nạp ảnh/video thì không vẽ màn hình chờ nữa
        if self.image_item is not None:
            return
            
        # -------------------------------------------------------------
        # VẼ MÀN HÌNH CHỜ (PLACEHOLDER)
        # -------------------------------------------------------------
        painter.save()
        
        # [BÍ QUYẾT]: Reset Transform để Icon và Text KHÔNG bị phóng to/nhỏ khi lăn chuột Zoom.
        # Nó sẽ dùng tọa độ pixel thực tế của Viewport màn hình.
        painter.setTransform(QTransform())
        
        # Lấy kích thước khung nhìn hiện tại để tìm tâm điểm
        view_rect = self.viewport().rect()
        center_x = view_rect.center().x()
        center_y = view_rect.center().y()
        
        # 1. Vẽ Icon (Sử dụng icon folder.png từ thư mục assets của bạn)
        from utils import paths
        icon_path = os.path.join(paths.ICONS_DIR, "not_found.png") # Bạn có thể đổi tên icon nếu muốn
        icon_size = 48
        
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(
                icon_size, icon_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            # Giảm độ mờ (Opacity) xuống 50% để trông "chìm" và tinh tế hơn
            painter.setOpacity(0.5) 
            painter.drawPixmap(
                int(center_x - icon_size / 2), 
                int(center_y - icon_size / 2 - 15), # Dịch lên trên một chút để nhường chỗ cho chữ
                pixmap
            )
        
        # 2. Vẽ Văn bản (Text)
        painter.setOpacity(1.0) # Phục hồi độ mờ cho chữ
        painter.setPen(QColor("#777777")) # Chữ màu xám
        
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        
        text = "Vui lòng, nạp lại nguồn video"
        
        # Tính toán chiều dài của chuỗi chữ để canh nó vào chính giữa hoàn hảo
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(text)
        
        painter.drawText(
            int(center_x - text_width / 2), 
            int(center_y + icon_size / 2 + 15), 
            text
        )
        
        painter.restore()


    def load_image(self, filepath: str):
        """Tải ảnh nền lên Canvas"""
        if not os.path.exists(filepath):
            print(f"Lỗi: Không tìm thấy ảnh {filepath}")
            return

        pixmap = QPixmap(filepath)
        
        # Xóa ảnh cũ nếu có
        if self.image_item:
            self.scene.removeItem(self.image_item)
            
        # Thêm ảnh mới vào dưới cùng (ZValue = -1)
        self.image_item = self.scene.addPixmap(pixmap)
        self.image_item.setZValue(-1)
        
        # Cập nhật kích thước Scene bằng kích thước ảnh thật
        self.scene.setSceneRect(self.image_item.boundingRect())
        # Tự động thu phóng cho vừa khung view
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # =========================================================================
    # XỬ LÝ SỰ KIỆN CHUỘT VÀ BÀN PHÍM
    # =========================================================================

    def wheelEvent(self, event: QWheelEvent):
        """Lăn chuột để Zoom"""
        if self.current_mode == "DRAW":
            return 
            
        zoom_step = 10 
        if event.angleDelta().y() > 0:
            self.current_zoom = min(500, self.current_zoom + zoom_step)
        else:
            self.current_zoom = max(10, self.current_zoom - zoom_step)
            
        self.set_zoom(self.current_zoom)
        self.zoom_level_changed.emit(self.current_zoom)
        
        # Báo cho Event biết là ta đã xử lý xong (tránh PyQt tự động scroll thêm)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if not self.image_item:
            return
        scene_pos = self.mapToScene(event.pos())

        # VẼ ĐỈNH BẰNG CHUỘT TRÁI (Bản CAD thông minh)
        if self.current_mode == "DRAW_POLYGON" and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            
            # Tái sử dụng nếu nam châm hút dính
            if getattr(self, 'snapped_node', None):
                new_node = self.snapped_node
            else:   
                new_node = NodeItem(scene_pos.x(), scene_pos.y())
                self.scene.addItem(new_node)
                self.all_nodes.append(new_node)
            
            # Nối cạnh
            if self.current_drawing_nodes:
                last_node = self.current_drawing_nodes[-1]
                if last_node != new_node:
                    edge = EdgeItem(last_node, new_node)
                    self.scene.addItem(edge)
                    last_node.add_edge(edge)
                    new_node.add_edge(edge)
                    self.current_drawing_edges.append(edge)
            
            # Cập nhật danh sách điểm đang vẽ
            if not self.current_drawing_nodes or self.current_drawing_nodes[-1] != new_node:
                self.current_drawing_nodes.append(new_node)

        
        elif self.current_mode == "DRAW_BBOX" and event.button() == Qt.MouseButton.LeftButton:
            self.bbox_start_pos = scene_pos
            
            if self.drawing_bbox is not None:
                self.scene.removeItem(self.drawing_bbox)

            self.drawing_bbox = self.scene.addRect(
                scene_pos.x(), scene_pos.y(), 0, 0, 
                QPen(QColor(255, 0, 0), 2)
            )
        elif self.current_mode == "DRAW_LINE" and event.button() == Qt.MouseButton.LeftButton:
            # 1. Tạo hoặc hút dính vào Đỉnh thứ nhất
            if self.line_start_pos is None:
                if getattr(self, 'snapped_node', None):
                    self.line_start_node = self.snapped_node
                else:
                    self.line_start_node = NodeItem(scene_pos.x(), scene_pos.y())
                    self.scene.addItem(self.line_start_node)
                    self.all_nodes.append(self.line_start_node)
                    
                self.line_start_pos = self.line_start_node.sceneBoundingRect().center()
            else:
                # 2. Tạo hoặc hút dính vào Đỉnh thứ hai
                if getattr(self, 'snapped_node', None):
                    line_end_node = self.snapped_node
                else:
                    line_end_node = NodeItem(scene_pos.x(), scene_pos.y())
                    self.scene.addItem(line_end_node)
                    self.all_nodes.append(line_end_node)

                import uuid
                entity_id = f"LINE_{str(uuid.uuid4())[:8].upper()}"
                
                # Tạo thực thể đường thẳng kết nối 2 Đỉnh
                line_entity = LineEntity(self.line_start_node, line_end_node, entity_id)
                self.scene.addItem(line_entity)
                
                # Đăng ký liên kết để khi di chuyển Đỉnh -> Đường thẳng tự co giãn theo
                self.line_start_node.add_edge(line_entity)
                line_end_node.add_edge(line_entity)
                
                print(f"[DRAW] Đã tạo Đoạn thẳng ID: {entity_id}")
                self.line_completed.emit((entity_id, line_entity))
                
                # Reset trạng thái
                self.line_start_pos = None
                self.line_start_node = None
                if self.ghost_line:
                    self.scene.removeItem(self.ghost_line)
                    self.ghost_line = None

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        super().mouseMoveEvent(event)
        scene_pos = self.mapToScene(event.pos())
        
        # [THÊM MỚI]: Kéo giãn Bbox theo chuột
        if self.current_mode == "DRAW_BBOX" and self.bbox_start_pos and self.drawing_bbox:
            x = min(self.bbox_start_pos.x(), scene_pos.x())
            y = min(self.bbox_start_pos.y(), scene_pos.y())
            w = abs(scene_pos.x() - self.bbox_start_pos.x())
            h = abs(scene_pos.y() - self.bbox_start_pos.y())
            self.drawing_bbox.setRect(x, y, w, h)

        if self.current_mode == "DRAW_POLYGON":
            
            # --- THUẬT TOÁN NAM CHÂM HÚT DÍNH (MAGNETIC SNAPPING) ---
            snap_distance = 15.0 # Khoảng cách hút (pixel)
            self.snapped_node = None
            
            for node in self.all_nodes:
                # Tính khoảng cách từ chuột đến tâm của Node
                node_center = node.sceneBoundingRect().center()
                dist = math.hypot(scene_pos.x() - node_center.x(), scene_pos.y() - node_center.y())
                
                if dist < snap_distance:
                    self.snapped_node = node
                    scene_pos = node_center # Ép tọa độ chuột dính chặt vào Node
                    break # Ưu tiên node đầu tiên tìm thấy
            
            # Đổi màu trỏ chuột ảo để báo hiệu đã hút dính thành công (UX)
            if self.snapped_node:
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            else:
                self.viewport().setCursor(Qt.CursorShape.CrossCursor)

            # Cập nhật đường nối ảo
            if self.current_drawing_nodes:
                last_node = self.current_drawing_nodes[-1]
                last_center = last_node.sceneBoundingRect().center()
                
                if not self.ghost_line:
                    self.ghost_line = self.scene.addLine(last_center.x(), last_center.y(), scene_pos.x(), scene_pos.y(), QPen(QColor(0, 255, 255), 2))
                else:
                    self.ghost_line.setLine(last_center.x(), last_center.y(), scene_pos.x(), scene_pos.y())

        elif self.current_mode == "DRAW_BBOX" and self.bbox_start_pos and self.drawing_bbox:          
            pass

        elif self.current_mode == "DRAW_LINE" and self.line_start_pos is not None:
            p1 = self.line_start_pos
            if not self.ghost_line:
                self.ghost_line = self.scene.addLine(p1.x(), p1.y(), scene_pos.x(), scene_pos.y(), QPen(QColor(255, 165, 0), 2))
            else:
                self.ghost_line.setLine(p1.x(), p1.y(), scene_pos.x(), scene_pos.y())        


    def keyPressEvent(self, event):
        if self.current_mode != "DRAW_POLYGON":
            super().keyPressEvent(event)
            return

        # 1. NÚT BACKSPACE: Xóa đỉnh cuối cùng vừa tạo
        if event.key() == Qt.Key.Key_Backspace:
            if not self.current_drawing_nodes:
                return

            popped_node = self.current_drawing_nodes.pop()
            
            # Xóa cạnh nối với nó (nếu có)
            if self.current_drawing_edges:
                popped_edge = self.current_drawing_edges.pop()
                self.scene.removeItem(popped_edge)
                popped_node.remove_edge(popped_edge)
                if self.current_drawing_nodes:
                    self.current_drawing_nodes[-1].remove_edge(popped_edge)

            # Nếu Node này MỚI TẠO (chưa được tái sử dụng bởi hình khác) -> Xóa hẳn khỏi màn hình
            if not popped_node.connected_edges:
                self.scene.removeItem(popped_node)
                self.all_nodes.remove(popped_node)

            # Ẩn đường ảo nếu hết điểm
            if not self.current_drawing_nodes and self.ghost_line:
                self.scene.removeItem(self.ghost_line)
                self.ghost_line = None

        # 2. NÚT ENTER: Khép kín đa giác và Lưu
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if len(self.current_drawing_nodes) >= 3:
                first_node = self.current_drawing_nodes[0]
                last_node = self.current_drawing_nodes[-1]
                
                if first_node != last_node:
                    edge = EdgeItem(last_node, first_node)
                    self.scene.addItem(edge)
                    last_node.add_edge(edge)
                    first_node.add_edge(edge)
                    self.current_drawing_edges.append(edge)

                entity_id = f"OBJ_{str(uuid.uuid4())[:8].upper()}"
                
                # [CẬP NHẬT 3]: Truyền cả danh sách các cạnh (edges) vào PolygonEntity
                poly_entity = PolygonEntity(
                    list(self.current_drawing_nodes), 
                    list(self.current_drawing_edges), # Gửi mảng cạnh
                    entity_id
                )
                self.scene.addItem(poly_entity)
                
                for node in self.current_drawing_nodes:
                    node.parent_polygon = poly_entity

                print(f"[DRAW] Đã tạo Polygon ID: {entity_id} với {len(self.current_drawing_edges)} cạnh.")
                
                self.polygon_completed.emit((entity_id, poly_entity))
                
                self.current_drawing_nodes.clear()
                self.current_drawing_edges.clear()
                if self.ghost_line:
                    self.scene.removeItem(self.ghost_line)
                    self.ghost_line = None

        if event.key() == Qt.Key.Key_Delete:
            selected_items = self.scene.selectedItems()
            for item in selected_items:
                if isinstance(item, LineEntity):
                    entity_id = item.entity_id
                    
                    # Giải phóng liên kết ở các đỉnh đầu mút
                    item.start_node.remove_edge(item)
                    item.end_node.remove_edge(item)
                    
                    # Nếu các đỉnh này không còn liên kết với cạnh nào khác -> Xóa đỉnh luôn cho sạch
                    for node in [item.start_node, item.end_node]:
                        if not node.connected_edges:
                            self.scene.removeItem(node)
                            if node in self.all_nodes:
                                self.all_nodes.remove(node)
                                
                    self.scene.removeItem(item)
                    self.item_deleted.emit(entity_id) # Phát tín hiệu xóa lên Controller
                    print(f"[DELETE]: Đã xóa đường thẳng {entity_id}")
            return
        super().keyPressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        # [FIXED]: Cập nhật logic nhả chuột (Release) cho Bbox
        if self.current_mode == "DRAW_BBOX" and event.button() == Qt.MouseButton.LeftButton:
            if self.drawing_bbox and self.bbox_start_pos:
                rect = self.drawing_bbox.rect()
                
                # Kiểm tra tránh click nhầm 1 điểm (chiều dài/rộng < 5px)
                if rect.width() > 5 and rect.height() > 5:
                    import uuid
                    entity_id = f"LIGHT_{str(uuid.uuid4())[:8].upper()}"
                    
                    # Tạo thực thể BboxEntity xịn (Có ID và fill màu đỏ mờ)
                    bbox_entity = BboxEntity(rect, entity_id)
                    self.scene.addItem(bbox_entity)
                    
                    print(f"[DRAW] Đã tạo Bbox Đèn ID: {entity_id}")
                    
                    # Phát tín hiệu lên Controller
                    self.bbox_completed.emit((entity_id, bbox_entity))
                
                # Xóa cái khung vẽ nháp đi
                self.scene.removeItem(self.drawing_bbox)
                self.drawing_bbox = None
                self.bbox_start_pos = None
                
                # Vẽ xong 1 cái thì tự thoát mode, nhường chỗ cho chuột pan ảnh
                self.set_mode("NONE")

        # Xử lý thả chuột giữa (Pan ảnh)
        if event.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
        super().mouseReleaseEvent(event)

    def _cancel_drawing(self):
        """Hủy bỏ hình đang vẽ dở dang (Dọn dẹp rác bộ nhớ)"""
        # 1. Xóa các cạnh đang vẽ dở khỏi Scene
        for edge in self.current_drawing_edges:
            self.scene.removeItem(edge)
        self.current_drawing_edges.clear()

        # 2. Xóa các đỉnh (nodes) đang vẽ dở khỏi Scene và mảng tổng
        for node in self.current_drawing_nodes:
            # Chỉ xóa những đỉnh mới tạo (không có kết nối với hình khác)
            if not node.connected_edges:
                self.scene.removeItem(node)
                if node in self.all_nodes:
                    self.all_nodes.remove(node)
        self.current_drawing_nodes.clear()

        # 3. Xóa đường line ảo bám theo chuột
        if self.ghost_line:
            self.scene.removeItem(self.ghost_line)
            self.ghost_line = None

        print("[CANVAS] Đã hủy bỏ nét vẽ dở dang.")

    def _finish_drawing(self):
        """Dọn dẹp các đường ảo, biến hình vẽ tạm thành hình vẽ thật"""
        self.is_drawing = False
        self.current_points.clear()
        
        if self.ghost_line:
            self.scene.removeItem(self.ghost_line)
            self.ghost_line = None
            
    def set_mode(self, mode: str):
        self.current_mode = mode
        
        # Chấp nhận cả chế độ vẽ Đa giác và vẽ Đoạn thẳng
        if mode in ["DRAW_POLYGON", "DRAW_LINE"]: 
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            
        elif mode == "ZOOM":
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.viewport().unsetCursor() 
            
        elif mode == "DRAW_BBOX": # Chế độ vẽ Đèn giao thông
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
            
        else: # "NONE"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)

    def set_zoom(self, zoom_percent: int):
        """Nhận % zoom từ Slider hoặc Lăn chuột và áp dụng vào ảnh"""
        self.current_zoom = zoom_percent
        scale_factor = zoom_percent / 100.0
        
        # [CẬP NHẬT RÀO CHẮN ZOOM]:
        # Để đảm bảo Scale Factor của lăn chuột được áp dụng độc lập,
        # Ta KHÔNG DÙNG transform.scale() cộng dồn, mà ta set cứng một Transform mới hoàn toàn.
        
        transform = QTransform()
        transform.scale(scale_factor, scale_factor)
        self.setTransform(transform)          

    def set_frame(self, frame_np: np.ndarray, vehicles_list: list = []): # Nhận thêm danh sách xe
        if frame_np is None:
            # Nếu video dừng, dọn dẹp sạch toàn bộ xe đồ họa trên màn hình
            for v_group in list(self.visual_vehicles.values()):
                v_group.remove_from_scene()
            self.visual_vehicles.clear()
            return
        
        frame_rgb = frame_np[:, :, ::-1] 
        h, w, ch = frame_rgb.shape
        bytes_per_line = ch * w
        frame_bytes = frame_rgb.tobytes()
        
        from PyQt6.QtGui import QImage, QPixmap
        q_image = QImage(frame_bytes, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)

        if self.image_item is None:
            self.image_item = self.scene.addPixmap(pixmap)
            self.image_item.setZValue(-1)
            # [ĐÃ XÓA self.recenter_and_fit() Ở ĐÂY VÌ CONTROLLER ĐÃ LÀM VIỆC ĐÓ]
        else:
            self.image_item.setPixmap(pixmap)
        
        self.sync_ai_visuals(vehicles_list)

    @pyqtSlot()
    def recenter_and_fit(self):
        """Reset Zoom/Pan và ép ảnh vừa vặn chính giữa màn hình"""
        if self.image_item is None:
            return
            
        self.resetTransform()
        
        img_rect = self.image_item.boundingRect()
        self.scene.setSceneRect(img_rect)
        
        self.fitInView(img_rect, Qt.AspectRatioMode.KeepAspectRatio)
        
        # [CẬP NHẬT 1]: Tính toán % Zoom thực tế để hiển thị lên Slider cho chuẩn
        # Thay vì gán cứng 100%, ta tính tỷ lệ scale hiện tại
        transform = self.transform()
        scale_x = transform.m11() # Hệ số scale trục X
        real_zoom_percent = int(scale_x * 100)
        
        self.current_zoom = real_zoom_percent
        self.zoom_level_changed.emit(self.current_zoom)

    def resizeEvent(self, event):
        """Tự động giữ ảnh ở giữa khi phóng to/thu nhỏ cửa sổ ứng dụng"""
        super().resizeEvent(event)
        # Chỉ tự động căn giữa nếu ảnh nhỏ hơn màn hình, hoặc bạn có thể bỏ dòng này 
        # nếu muốn người dùng được quyền để lệch khi Resize
        # self.recenter_and_fit() 

    def sync_ai_visuals(self, vehicles_list: list):
        """
        [TRÁI TIM ĐỒ HỌA VECTOR]: Đồng bộ hóa trạng thái xe AI với các lớp PyQt6.
        Tự động tạo mới, cập nhật tọa độ, xóa xe mất dấu và áp dụng bộ lọc tức thời.
        """
        seen_ids = set()
        
        for vehicle in vehicles_list:
            v_id = vehicle.id
            seen_ids.add(v_id)
            
            # 1. Nếu xe mới xuất hiện -> Tạo mới lớp vẽ Vector
            if v_id not in self.visual_vehicles:
                self.visual_vehicles[v_id] = VehicleVisualGroup(self.scene, v_id, vehicle.vehicle_type)
                
            visual_group = self.visual_vehicles[v_id]
            
            # 2. Cập nhật vị trí, vệt đuôi và màu viền dựa trên trạng thái vi phạm
            is_violating = len(vehicle.active_violations) > 0
            is_pending = len(getattr(vehicle, 'pending_violations', set())) > 0
            trajectory = list(vehicle.coordinate.full_trajectory)
            
            visual_group.update_state(
                bbox=vehicle.current_bbox,
                trajectory=trajectory,
                is_violating=is_violating,
                is_pending=is_pending,
                show_trail=self.visual_filters["show_trails"]
            )
            
            # 3. ÁP DỤNG BỘ LỌC TỨC THÌ (Real-time Filtering)
            is_visible = True
            v_type = vehicle.vehicle_type
            
            # Bộ lọc theo loại xe
            from utils.enums import TrafficVehicleType
            if v_type in [TrafficVehicleType.CAR, TrafficVehicleType.TRUCK, TrafficVehicleType.BUS] and not self.visual_filters["show_cars"]:
                is_visible = False
            elif v_type == TrafficVehicleType.MOTORCYCLE and not self.visual_filters["show_motorcycles"]:
                is_visible = False
                
            # Bộ lọc chỉ hiện xe vi phạm
            if self.visual_filters["show_violators_only"] and not (is_violating or is_pending):
                is_visible = False
                
            visual_group.set_visible(is_visible)

        # 4. DỌN DẸP: Xóa các xe đã rời khỏi màn hình
        active_ids = list(self.visual_vehicles.keys())
        for vid in active_ids: # [FIXED LỖI CÚ PHÁP]: Sử dụng vòng lặp tiêu chuẩn
            if vid not in seen_ids:
                self.visual_vehicles[vid].remove_from_scene()
                del self.visual_vehicles[vid]
