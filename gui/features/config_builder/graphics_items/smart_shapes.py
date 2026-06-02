from PyQt6.QtWidgets import (
    QGraphicsPolygonItem, QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen, QBrush, QColor, QPolygonF

class PolygonEntity(QGraphicsPolygonItem):
    """
    Thực thể Đa giác bao trùm toàn bộ các Node và Edge. 
    Dùng để Fill màu (Highlight) khi người dùng Hover chuột từ Right Panel.
    """
    def __init__(self, nodes, edges, entity_id, parent=None):
        super().__init__(parent)
        self.nodes = nodes
        self.edges = edges # Lưu danh sách các EdgeItem tạo nên đa giác này
        self.entity_id = entity_id
        
        self.setZValue(0)
        self.setPen(QPen(Qt.GlobalColor.transparent))
        
        self.default_brush = QBrush(QColor(0, 255, 255, 0))
        self.highlight_brush = QBrush(QColor(0, 122, 204, 100))
        
        self.setBrush(self.default_brush)
        self.update_shape()

    def update_shape(self):
        polygon = QPolygonF()
        for node in self.nodes:
            polygon.append(node.sceneBoundingRect().center())
        self.setPolygon(polygon)
        
    def set_highlight(self, is_highlighted: bool):
        """Highlight toàn bộ đa giác"""
        self.setBrush(self.highlight_brush if is_highlighted else self.default_brush)
        
    def highlight_sub_edge(self, edge_index: int, is_highlighted: bool):
        """[THÊM MỚI]: Bật sáng 1 cạnh cụ thể bên trong đa giác"""
        if 0 <= edge_index < len(self.edges):
            self.edges[edge_index].set_highlight(is_highlighted)

class EdgeItem(QGraphicsLineItem):
    """Cạnh nối 2 đỉnh. Tự động thay đổi khi đỉnh bị kéo thả."""
    def __init__(self, start_node, end_node, parent=None):
        super().__init__(parent)
        self.start_node = start_node
        self.end_node = end_node

        self.default_pen = QPen(QColor(0, 255, 255), 2) # Cyan, dày 2
        self.highlight_pen = QPen(QColor(255, 255, 0), 4) # Vàng, dày 4 (Sáng rực lên)

        self.setPen(QPen(QColor(0, 255, 255), 2)) # Màu cyan
        self.setZValue(1) # Nằm dưới các đỉnh
        self.update_position()

    def update_position(self):
        self.setLine(self.start_node.sceneBoundingRect().center().x(),
                     self.start_node.sceneBoundingRect().center().y(),
                     self.end_node.sceneBoundingRect().center().x(),
                     self.end_node.sceneBoundingRect().center().y())
                     
    def set_highlight(self, is_highlighted: bool):
        """Hàm bật/tắt viền sáng cho cạnh này"""
        self.setPen(self.highlight_pen if is_highlighted else self.default_pen)
        self.setZValue(3 if is_highlighted else 1) # Đẩy cạnh sáng lên trên cùng

class NodeItem(QGraphicsEllipseItem):
    """Đỉnh đa giác. Có thể kéo thả, có thể tái sử dụng."""
    def __init__(self, x, y, parent=None):
        # Tạo vòng tròn bán kính 5px (đường kính 10)
        super().__init__(x - 5, y - 5, 10, 10, parent)
        self.setBrush(QBrush(QColor(255, 0, 0))) # Màu đỏ
        self.setPen(QPen(Qt.GlobalColor.transparent))
        
        # Bật tính năng cho phép Kéo thả và Gửi sự kiện di chuyển
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(2) # Nằm trên các cạnh
        
        self.connected_edges = [] # Lưu các cạnh gắn với đỉnh này
        self.parent_polygon: PolygonEntity = None

    def add_edge(self, edge: EdgeItem):
        self.connected_edges.append(edge)

    def remove_edge(self, edge: EdgeItem):
        if edge in self.connected_edges:
            self.connected_edges.remove(edge)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.connected_edges:
                edge.update_position()
            # [CẬP NHẬT]: Cập nhật cả vùng fill màu của đa giác mẹ
            if self.parent_polygon:
                self.parent_polygon.update_shape()
        return super().itemChange(change, value)
    
class BboxEntity(QGraphicsRectItem):
    """Thực thể Bounding Box dùng cho Đèn giao thông"""
    def __init__(self, rect, entity_id, parent=None):
        super().__init__(rect, parent)
        self.entity_id = entity_id
        self.setPen(QPen(QColor(255, 0, 0), 2)) # Viền đỏ
        self.setBrush(QBrush(QColor(255, 0, 0, 50))) # Nền đỏ mờ

        self.default_pen = QPen(QColor(255, 0, 0), 2)       # Viền đỏ dày 2
        self.highlight_pen = QPen(QColor(255, 255, 0), 4)    # Viền vàng dày 4
        
        self.default_brush = QBrush(QColor(255, 0, 0, 50))   # Nền đỏ mờ
        self.highlight_brush = QBrush(QColor(255, 0, 0, 120)) # Nền đỏ đậm hơn
        
        self.setPen(self.default_pen)
        self.setBrush(self.default_brush)
    
    def set_highlight(self, is_highlighted: bool):
        self.setPen(self.highlight_pen if is_highlighted else self.default_pen)
        self.setBrush(self.highlight_brush if is_highlighted else self.default_brush)
        self.setZValue(3 if is_highlighted else 0)

class LineEntity(QGraphicsLineItem):
    """Thực thể Đường thẳng thông minh. Tự động co giãn khi đỉnh đầu mút bị kéo thả."""
    def __init__(self, start_node, end_node, entity_id, parent=None):
        super().__init__(parent)
        self.start_node = start_node
        self.end_node = end_node
        self.entity_id = entity_id
        
        self.default_pen = QPen(QColor(255, 165, 0), 2) # Cam, dày 2
        self.highlight_pen = QPen(QColor(255, 255, 0), 4) # Vàng, dày 4
        
        self.setPen(self.default_pen)
        self.setZValue(1) # Nằm dưới đỉnh
        
        # [QUAN TRỌNG]: Cho phép người dùng click chọn đường thẳng để bấm Delete xóa
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        self.update_position()

    def update_position(self):
        """Cập nhật tọa độ dựa trên tâm của 2 đỉnh đầu mút"""
        self.setLine(self.start_node.sceneBoundingRect().center().x(),
                     self.start_node.sceneBoundingRect().center().y(),
                     self.end_node.sceneBoundingRect().center().x(),
                     self.end_node.sceneBoundingRect().center().y())
                     
    def set_highlight(self, is_highlighted: bool):
        self.setPen(self.highlight_pen if is_highlighted else self.default_pen)
        self.setZValue(3 if is_highlighted else 1)
