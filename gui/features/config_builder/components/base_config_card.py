# --- START OF FILE gui/features/config_builder/components/base_config_card.py ---
import os
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QIcon

class BaseConfigCard(QFrame):
    """
    Lớp cơ sở định nghĩa UI chung (Header, Title, Nút xóa) cho các Thẻ Cấu hình.
    """
    # Chỉ giữ lại tín hiệu xóa UI cục bộ (Panel sẽ hứng tín hiệu này để gỡ Widget)
    request_delete = pyqtSignal(object)

    def __init__(self, title: str, icon_name: str, bg_color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ConfigCard")
        
        self.setStyleSheet(f"""
            #ConfigCard {{
                background-color: {bg_color};
                border: 1px solid #555;
                border-radius: 5px;
                margin-bottom: 5px;
            }}
            QLabel {{ 
                color: #cccccc; 
                background-color: transparent; 
                border: none;
                font-weight: bold
            }}
        """)
        self._setup_base_ui(title, icon_name)

    def _setup_base_ui(self, title: str, icon_name: str):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(6)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.abspath(os.path.join(current_dir, "../../../assets/icons", icon_name))

        lbl_icon = QLabel()
        lbl_icon.setPixmap(QPixmap(icon_path).scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        lbl_icon.setFixedWidth(16)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px; background-color: transparent;")

        btn_delete = QPushButton()
        btn_delete.setIcon(QIcon(os.path.join(os.path.dirname(icon_path), "delete.png")))
        btn_delete.setFixedSize(20, 20)
        btn_delete.setStyleSheet("border-radius: 10px; font-weight: bold; color: white;")
        btn_delete.clicked.connect(lambda: self.request_delete.emit(self))

        header_layout.addWidget(lbl_icon)
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(btn_delete)
        self.main_layout.addLayout(header_layout)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        self.main_layout.addLayout(self.content_layout)