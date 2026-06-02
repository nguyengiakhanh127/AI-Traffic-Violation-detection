# --- START OF FILE gui/shared_components/collapsible_sidebar.py ---
from PyQt6.QtWidgets import QFrame
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtProperty, QEvent

class CollapsibleSidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SideBar")
        
        # Cấu hình kích thước
        self.min_width = 55   # Kích thước khi thu nhỏ (Chỉ đủ chứa Icon)
        self.max_width = 200  # Kích thước khi mở rộng (Chứa cả Icon + Text)
        
        self.setFixedWidth(self.min_width) # Mặc định khởi động là thu nhỏ

        # Khởi tạo bộ tạo hiệu ứng động (Animation)
        # Bắt buộc phải truyền b"sidebarWidth" (dạng byte string)
        self.animation = QPropertyAnimation(self, b"sidebarWidth")
        self.animation.setDuration(200) # Tốc độ hiệu ứng: 200 mili-giây
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine) # Hiệu ứng mượt ở hai đầu

    # =========================================================================
    # ĐỊNH NGHĨA THUỘC TÍNH TÙY CHỈNH ĐỂ PYQT6 CÓ THỂ ANIMATE CHIỀU RỘNG
    # =========================================================================
    @pyqtProperty(int)
    def sidebarWidth(self):
        return self.width()

    @sidebarWidth.setter
    def sidebarWidth(self, width):
        self.setFixedWidth(width)

    # =========================================================================
    # BẮT SỰ KIỆN CHUỘT (HOVER EVENTS)
    # =========================================================================
    def enterEvent(self, event):
        """Khi người dùng rê chuột vào Sidebar -> Mở rộng"""
        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(self.max_width)
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Khi người dùng đưa chuột ra khỏi Sidebar -> Tự động thu nhỏ"""
        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(self.min_width)
        self.animation.start()
        super().leaveEvent(event)

# --- END OF FILE gui/shared_components/collapsible_sidebar.py ---