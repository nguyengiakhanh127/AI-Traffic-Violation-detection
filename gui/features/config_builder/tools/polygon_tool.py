import math
import uuid
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QPen, QColor
from gui.features.config_builder.tools.base_tool import BaseTool
from gui.features.config_builder.graphics_items.smart_shapes import PolygonEntity, EdgeItem, NodeItem

class PolygonTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.current_nodes = []
        self.current_edges = []
        self.ghost_line = None
        self.snapped_node = None

    def activate(self):
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event: QMouseEvent, scene_pos):
        if event.button() != Qt.MouseButton.LeftButton: return

        # 1. Tái sử dụng node nếu nam châm hút dính
        if self.snapped_node:
            new_node = self.snapped_node
        else:   
            new_node = NodeItem(scene_pos.x(), scene_pos.y())
            self.scene.addItem(new_node)
            self.canvas.all_nodes.append(new_node)
        
        # 2. Nối cạnh
        if self.current_nodes:
            last_node = self.current_nodes[-1]
            if last_node != new_node:
                edge = EdgeItem(last_node, new_node)
                self.scene.addItem(edge)
                last_node.add_edge(edge)
                new_node.add_edge(edge)
                self.current_edges.append(edge)
        
        if not self.current_nodes or self.current_nodes[-1] != new_node:
            self.current_nodes.append(new_node)

    def mouseMoveEvent(self, event: QMouseEvent, scene_pos):
        # 1. Logic nam châm hút dính (Magnetic Snapping)
        snap_distance = 15.0 
        self.snapped_node = None
        
        for node in self.canvas.all_nodes:
            node_center = node.sceneBoundingRect().center()
            if math.hypot(scene_pos.x() - node_center.x(), scene_pos.y() - node_center.y()) < snap_distance:
                self.snapped_node = node
                scene_pos = node_center 
                break 

        # 2. Cập nhật đường ảo (Ghost Line)
        if self.current_nodes:
            last_center = self.current_nodes[-1].sceneBoundingRect().center()
            if not self.ghost_line:
                self.ghost_line = self.scene.addLine(last_center.x(), last_center.y(), scene_pos.x(), scene_pos.y(), QPen(QColor(0, 255, 255), 2))
            else:
                self.ghost_line.setLine(last_center.x(), last_center.y(), scene_pos.x(), scene_pos.y())

    def keyPressEvent(self, event: QKeyEvent):
        # NÚT BACKSPACE: Xóa đỉnh cuối cùng
        if event.key() == Qt.Key.Key_Backspace:
            if not self.current_nodes: return
            popped_node = self.current_nodes.pop()
            
            if self.current_edges:
                popped_edge = self.current_edges.pop()
                self.scene.removeItem(popped_edge)
                popped_node.remove_edge(popped_edge)
                if self.current_nodes:
                    self.current_nodes[-1].remove_edge(popped_edge)

            if not popped_node.connected_edges:
                self.scene.removeItem(popped_node)
                self.canvas.all_nodes.remove(popped_node)

            if not self.current_nodes and self.ghost_line:
                self.scene.removeItem(self.ghost_line)
                self.ghost_line = None

        # NÚT ENTER: Khép kín đa giác
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            if len(self.current_nodes) >= 3:
                first_node, last_node = self.current_nodes[0], self.current_nodes[-1]
                if first_node != last_node:
                    edge = EdgeItem(last_node, first_node)
                    self.scene.addItem(edge)
                    last_node.add_edge(edge)
                    first_node.add_edge(edge)
                    self.current_edges.append(edge)

                entity_id = f"OBJ_{str(uuid.uuid4())[:8].upper()}"
                poly_entity = PolygonEntity(list(self.current_nodes), list(self.current_edges), entity_id)
                self.scene.addItem(poly_entity)
                
                for node in self.current_nodes:
                    node.parent_polygon = poly_entity

                # Phát tín hiệu qua Canvas
                self.canvas.polygon_completed.emit((entity_id, poly_entity))
                self.current_nodes.clear()
                self.current_edges.clear()
                self.cancel_drawing()

    def cancel_drawing(self):
        for edge in self.current_edges: self.scene.removeItem(edge)
        self.current_edges.clear()

        for node in self.current_nodes:
            if not node.connected_edges:
                self.scene.removeItem(node)
                if node in self.canvas.all_nodes: self.canvas.all_nodes.remove(node)
        self.current_nodes.clear()

        if self.ghost_line:
            self.scene.removeItem(self.ghost_line)
            self.ghost_line = None