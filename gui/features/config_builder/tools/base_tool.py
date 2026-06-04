from PyQt6.QtGui import QMouseEvent, QKeyEvent

class BaseTool:
    """Lớp nền tảng cho mọi công cụ tương tác trên Canvas"""
    def __init__(self, canvas):
        self.canvas = canvas
        self.scene = canvas.scene

    def activate(self):
        """Được gọi khi công cụ này được chọn (Bấm nút trên Toolbar)"""
        pass

    def deactivate(self):
        """Được gọi khi chuyển sang công cụ khác (Dọn dẹp rác đang vẽ dở)"""
        self.cancel_drawing()

    def mousePressEvent(self, event: QMouseEvent, scene_pos): pass
    def mouseMoveEvent(self, event: QMouseEvent, scene_pos): pass
    def mouseReleaseEvent(self, event: QMouseEvent, scene_pos): pass
    def keyPressEvent(self, event: QKeyEvent): pass
    
    def cancel_drawing(self):
        """Hủy bỏ thao tác đang vẽ dở dang"""
        pass