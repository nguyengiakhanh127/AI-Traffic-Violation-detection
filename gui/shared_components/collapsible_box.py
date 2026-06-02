# --- START UPDATE: gui/shared_components/collapsible_box.py ---
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QScrollArea, QSizePolicy
from PyQt6.QtCore import QPropertyAnimation, QAbstractAnimation, QParallelAnimationGroup, Qt
from PyQt6.QtGui import QIcon

class CollapsibleBox(QWidget):
    def __init__(self, title="", max_height: int = 400, parent=None):
        super().__init__(parent)
        self.max_height = max_height # Lưu lại ngưỡng trần
        
        # Thư mục chứa Icon
        self.icon_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")
        self.icon_down = QIcon(os.path.join(self.icon_dir, "arrow_down.png"))
        self.icon_up = QIcon(os.path.join(self.icon_dir, "arrow_up.png"))
        print((os.path.join(self.icon_dir, "arrow_down.png")))
        # 1. Nút tiêu đề (Tùy biến CSS để ép Text bên trái, Icon bên phải)
        self.toggle_button = QPushButton(title, self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setIcon(self.icon_down) # Mặc định mũi tên hướng xuống (đang đóng)
        
        # CSS thần thánh: Text-align left, đẩy padding-right ra để nhường chỗ cho Icon,
        # và cố định Icon nằm ở góc bên phải.
        self.toggle_button.setStyleSheet("""
            QPushButton {
                border: none; 
                font-weight: bold; 
                font-size: 14px;
                color: #e0e0e0;
                text-align: left;
                padding: 10px 5px;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        # Đảo vị trí Icon sang bên phải của chữ
        self.toggle_button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        
        self.toggle_button.pressed.connect(self._on_pressed)

        # 2. Vùng chứa nội dung (Giữ nguyên như cũ)
        self.content_area = QScrollArea(self)
        self.content_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_area.setMaximumHeight(0) 
        self.content_area.setMinimumHeight(0)

        self.toggle_animation = QParallelAnimationGroup(self)
        self.content_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.content_animation.setDuration(250) 
        self.toggle_animation.addAnimation(self.content_animation)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        self.content_layout.setSpacing(10)
        
        self.inner_content = QWidget()
        self.inner_content.setLayout(self.content_layout)
        self.content_area.setWidget(self.inner_content)
        self.content_area.setWidgetResizable(True)

    def set_content_layout(self, layout):
        QWidget().setLayout(self.content_layout) 
        self.content_layout = layout
        self.inner_content.setLayout(self.content_layout)

    def _on_pressed(self):
        checked = self.toggle_button.isChecked()
        
        self.toggle_button.setIcon(self.icon_up if not checked else self.icon_down)
        
        self.toggle_animation.setDirection(
            QAbstractAnimation.Direction.Forward if not checked else QAbstractAnimation.Direction.Backward
        )
        
        # Tính toán chiều cao thực tế của nội dung bên trong
        content_height = self.content_layout.sizeHint().height() + 15 # Đệm 15px cho rộng rãi
        
        # [CẬP NHẬT LOGIC ZOOM DROPDOWN]:
        # Nếu chiều cao vượt quá ngưỡng self.max_height, ta ghìm nó lại ở mức max_height.
        # Lúc này, QScrollArea bên trong sẽ tự động kích hoạt thanh cuộn dọc (Scrollbar) cho người dùng cuộn.
        target_height = min(content_height, self.max_height)
        
        self.content_animation.setStartValue(0)
        self.content_animation.setEndValue(target_height)
        
        self.toggle_animation.start()
