import uuid
import math
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QPen, QColor
from gui.features.config_builder.tools.base_tool import BaseTool
from gui.features.config_builder.graphics_items.smart_shapes import NodeItem, LineEntity

class LineTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.line_start_pos = None
        self.line_start_node = None
        self.ghost_line = None
        self.snapped_node = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event: QMouseEvent, scene_pos):
        if event.button() != Qt.MouseButton.LeftButton: return

        # CLIP 1: Click lần đầu để đánh dấu Đỉnh thứ nhất
        if self.line_start_pos is None:
            if getattr(self, 'snapped_node', None):
                self.line_start_node = self.snapped_node
            else:
                self.line_start_node = NodeItem(scene_pos.x(), scene_pos.y())
                self.scene.addItem(self.line_start_node)
                self.canvas.all_nodes.append(self.line_start_node)
                
            self.line_start_pos = self.line_start_node.sceneBoundingRect().center()
            
        # CLIP 2: Click lần 2 để chốt Đỉnh thứ hai và sinh ra Đường thẳng
        else:
            if getattr(self, 'snapped_node', None):
                line_end_node = self.snapped_node
            else:
                line_end_node = NodeItem(scene_pos.x(), scene_pos.y())
                self.scene.addItem(line_end_node)
                self.canvas.all_nodes.append(line_end_node)

            entity_id = f"LINE_{str(uuid.uuid4())[:8].upper()}"
            
            # Sinh ra Thực thể Đường thẳng thông minh nối 2 đỉnh
            line_entity = LineEntity(self.line_start_node, line_end_node, entity_id)
            self.scene.addItem(line_entity)
            
            # Khóa chặt đường thẳng vào 2 đỉnh để khi kéo đỉnh, đường sẽ chạy theo
            self.line_start_node.add_edge(line_entity)
            line_end_node.add_edge(line_entity)
            
            print(f"[DRAW] Đã tạo Đoạn thẳng ID: {entity_id}")
            self.canvas.line_completed.emit((entity_id, line_entity))
            
            # Dọn dẹp bản nháp
            self.cancel_drawing()
            self.canvas.set_mode("NONE")

    def mouseMoveEvent(self, event: QMouseEvent, scene_pos):
        # Thuật toán Nam châm hút dính (Snapping)
        snap_distance = 15.0 
        self.snapped_node = None
        
        for node in self.canvas.all_nodes:
            node_center = node.sceneBoundingRect().center()
            dist = math.hypot(scene_pos.x() - node_center.x(), scene_pos.y() - node_center.y())
            if dist < snap_distance:
                self.snapped_node = node
                scene_pos = node_center 
                break 
                
        # Vẽ đường nối nét đứt (ghost_line) bám theo con trỏ chuột
        if self.line_start_pos is not None:
            p1 = self.line_start_pos
            if not self.ghost_line:
                self.ghost_line = self.scene.addLine(p1.x(), p1.y(), scene_pos.x(), scene_pos.y(), QPen(QColor(255, 165, 0), 2))
            else:
                self.ghost_line.setLine(p1.x(), p1.y(), scene_pos.x(), scene_pos.y())

    def keyPressEvent(self, event: QKeyEvent):
        # Bấm nút ESC để hủy thao tác đang vẽ dở
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_drawing()
            self.canvas.set_mode("NONE")

    def cancel_drawing(self):
        self.line_start_pos = None
        
        # Nếu đỉnh thứ nhất mới được tạo ra (chưa gắn vào đâu) thì xóa luôn cho sạch
        if self.line_start_node and not self.line_start_node.connected_edges:
            self.scene.removeItem(self.line_start_node)
            if self.line_start_node in self.canvas.all_nodes:
                self.canvas.all_nodes.remove(self.line_start_node)
                
        self.line_start_node = None
        
        if self.ghost_line:
            self.scene.removeItem(self.ghost_line)
            self.ghost_line = None