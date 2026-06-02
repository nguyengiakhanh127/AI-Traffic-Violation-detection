from PyQt6.QtWidgets import QGraphicsScene, QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsPathItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen, QBrush, QColor, QPainterPath

class VehicleVisualGroup:
    """
    Quản lý các lớp đồ họa Vector của 1 phương tiện trên QGraphicsScene.
    Bao gồm: Hộp xe (Bbox), Nhãn tên (Label), và Vệt đuôi mờ (Trail).
    """
    def __init__(self, scene: QGraphicsScene, vehicle_id: int, vehicle_type):
        self.scene = scene
        self.vehicle_id = vehicle_id
        self.vehicle_type = vehicle_type
        
        # 1. Hộp nhận diện (Bbox)
        self.bbox_item = QGraphicsRectItem()
        self.bbox_item.setZValue(10)
        self.scene.addItem(self.bbox_item)
        
        # 2. Khung nền đen của Nhãn (Label BG)
        self.label_bg = QGraphicsRectItem()
        self.label_bg.setZValue(11)
        self.label_bg.setBrush(QBrush(QColor(0, 0, 0, 200))) # Đen mờ
        self.label_bg.setPen(QPen(Qt.GlobalColor.transparent))
        self.scene.addItem(self.label_bg)
        
        # 3. Chữ của Nhãn (Label Text)
        self.label_text = QGraphicsSimpleTextItem()
        self.label_text.setZValue(12)
        self.scene.addItem(self.label_text)
        
        # 4. Vệt đuôi di chuyển (Trail)
        self.trail_item = QGraphicsPathItem()
        self.trail_item.setZValue(8) # Nằm dưới xe
        self.scene.addItem(self.trail_item)

    def update_state(self, bbox: tuple, trajectory: list, is_violating: bool, is_pending: bool, show_trail: bool):
        """Cập nhật tọa độ và màu sắc động của các lớp vector theo từng frame"""
        x1, y1, x2, y2 = bbox
        w, h = x2 - x1, y2 - y1
        
        # Chọn màu sắc theo trạng thái vi phạm của xe
        if is_violating:
            color = QColor(255, 0, 0)      # Đỏ (Vi phạm)
        elif is_pending:
            color = QColor(255, 165, 0)    # Cam (Nghi vấn)
        else:
            color = QColor(0, 255, 0)      # Xanh lá (An toàn)
            
        # 1. Cập nhật Bbox
        self.bbox_item.setRect(x1, y1, w, h)
        self.bbox_item.setPen(QPen(color, 2))
        
        # 2. Cập nhật chữ Nhãn
        text_str = f"#{self.vehicle_id} {self.vehicle_type.name}"
        self.label_text.setText(text_str)
        self.label_text.setBrush(QBrush(QColor(255, 255, 255))) # Chữ trắng
        self.label_text.setPos(x1 + 4, y1 - 18)
        
        # 3. Cập nhật nền đen của nhãn khớp khít với kích thước chữ
        text_rect = self.label_text.boundingRect()
        self.label_bg.setRect(x1, y1 - 20, text_rect.width() + 8, 18)
        self.label_bg.setPen(QPen(color, 1)) # Viền màu theo trạng thái xe
        
        # 4. Cập nhật vệt đuôi bánh xe (Trajectory)
        if show_trail and len(trajectory) >= 2:
            path = QPainterPath()
            path.moveTo(trajectory[0].x, trajectory[0].y)
            for pt in trajectory[1:]:
                path.lineTo(pt.x, pt.y)
            self.trail_item.setPath(path)
            self.trail_item.setPen(QPen(QColor(255, 0, 0, 150), 2, Qt.PenStyle.DashLine))
            self.trail_item.show()
        else:
            self.trail_item.hide()

    def set_visible(self, visible: bool):
        """Ẩn/Hiện toàn bộ nhóm đồ họa này"""
        self.bbox_item.setVisible(visible)
        self.label_bg.setVisible(visible)
        self.label_text.setVisible(visible)
        self.trail_item.setVisible(visible if self.trail_item.isVisible() else False)

    def remove_from_scene(self):
        """Dọn dẹp khỏi Scene khi xe biến mất"""
        self.scene.removeItem(self.bbox_item)
        self.scene.removeItem(self.label_bg)
        self.scene.removeItem(self.label_text)
        self.scene.removeItem(self.trail_item)
