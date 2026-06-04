import uuid
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent, QKeyEvent, QPen, QColor
from gui.features.config_builder.tools.base_tool import BaseTool
from gui.features.config_builder.graphics_items.smart_shapes import BboxEntity

class BboxTool(BaseTool):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.drawing_bbox = None
        self.bbox_start_pos = None

    def activate(self):
        # Đổi con trỏ thành dấu cộng khi bắt đầu vẽ
        self.canvas.viewport().setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event: QMouseEvent, scene_pos):
        if event.button() != Qt.MouseButton.LeftButton: return

        self.bbox_start_pos = scene_pos
        
        # Nếu đang có khung nháp cũ, xóa đi
        if self.drawing_bbox is not None:
            self.scene.removeItem(self.drawing_bbox)

        # Vẽ một khung chữ nhật nháp (viền đỏ) tại vị trí click chuột
        self.drawing_bbox = self.scene.addRect(
            scene_pos.x(), scene_pos.y(), 0, 0, 
            QPen(QColor(255, 0, 0), 2)
        )

    def mouseMoveEvent(self, event: QMouseEvent, scene_pos):
        # Kéo dãn khung chữ nhật theo con trỏ chuột
        if self.bbox_start_pos and self.drawing_bbox:
            x = min(self.bbox_start_pos.x(), scene_pos.x())
            y = min(self.bbox_start_pos.y(), scene_pos.y())
            w = abs(scene_pos.x() - self.bbox_start_pos.x())
            h = abs(scene_pos.y() - self.bbox_start_pos.y())
            self.drawing_bbox.setRect(x, y, w, h)

    def mouseReleaseEvent(self, event: QMouseEvent, scene_pos):
        if event.button() != Qt.MouseButton.LeftButton: return
        
        # Chốt sổ Bounding Box khi nhả chuột
        if self.drawing_bbox and self.bbox_start_pos:
            rect = self.drawing_bbox.rect()
            
            # Chống lỗi người dùng vô tình click chuột sinh ra Bbox quá nhỏ (< 5 pixel)
            if rect.width() > 5 and rect.height() > 5:
                entity_id = f"LIGHT_{str(uuid.uuid4())[:8].upper()}"
                
                # Biến khung nháp thành Thực thể Bbox xịn (có fill màu đỏ mờ)
                bbox_entity = BboxEntity(rect, entity_id)
                self.scene.addItem(bbox_entity)
                
                print(f"[DRAW] Đã tạo Bbox Đèn ID: {entity_id}")
                
                # Báo cáo lên trên
                self.canvas.bbox_completed.emit((entity_id, bbox_entity))
            
            # Dọn dẹp bản nháp
            self.cancel_drawing()
            
            # Tự động thoát chế độ vẽ để người dùng không vô tình vẽ tiếp
            self.canvas.set_mode("NONE")

    def cancel_drawing(self):
        if self.drawing_bbox:
            self.scene.removeItem(self.drawing_bbox)
            self.drawing_bbox = None
        self.bbox_start_pos = None