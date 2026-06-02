# --- START OF FILE gui/shared_components/custom_titlebar.py ---
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent

class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setObjectName("TitleBar")
        self.setFixedHeight(40)
        
        # Biến phục vụ tính năng kéo thả cửa sổ
        self.is_moving = False
        self.drag_start_pos = QPoint()

        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 1. Logo + Tên App
        self.lbl_logo = QLabel("🚦 TRAFFIC AI SYSTEM")
        self.lbl_logo.setObjectName("AppLogo")
        
        # 2. Spacer (Đẩy các nút về góc phải)
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # 3. Các nút tiện ích (Minimize, Maximize, Close)
        self.btn_minimize = QPushButton("—")
        self.btn_maximize = QPushButton("◻")
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("BtnClose")

        # Gắn sự kiện cho nút
        self.btn_minimize.clicked.connect(self._minimize_window)
        self.btn_maximize.clicked.connect(self._maximize_window)
        self.btn_close.clicked.connect(self._close_window)

        # Thêm vào layout
        layout.addWidget(self.lbl_logo)
        layout.addSpacerItem(spacer)
        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_maximize)
        layout.addWidget(self.btn_close)

    # --- Các hàm xử lý sự kiện Nút bấm ---
    def _minimize_window(self):
        if self.parent_window:
            self.parent_window.showMinimized()

    def _maximize_window(self):
        if self.parent_window:
            if self.parent_window.isMaximized():
                self.parent_window.showNormal()
                self.btn_maximize.setText("◻")
            else:
                self.parent_window.showMaximized()
                self.btn_maximize.setText("❐")

    def _close_window(self):
        if self.parent_window:
            self.parent_window.close()

    # --- Các hàm xử lý sự kiện Kéo thả cửa sổ (Drag & Drop) ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_moving = True
            # Lấy vị trí click chuột tương đối so với cửa sổ
            self.drag_start_pos = event.globalPosition().toPoint() - self.parent_window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.is_moving and self.parent_window and not self.parent_window.isMaximized():
            # Di chuyển cửa sổ theo tọa độ chuột hiện tại trừ đi vị trí ban đầu
            self.parent_window.move(event.globalPosition().toPoint() - self.drag_start_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.is_moving = False
        event.accept()

    # Chống click đúp phóng to/thu nhỏ
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._maximize_window()
            event.accept()

# --- END OF FILE gui/shared_components/custom_titlebar.py ---