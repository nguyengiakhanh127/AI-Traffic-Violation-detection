# --- START OF FILE gui/features/violation_reviewer/reviewer_view.py ---
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PyQt6.QtCore import Qt

# Import 3 mảnh ghép Lego
from gui.features.violation_reviewer.components.filter_panel import FilterPanel
from gui.features.violation_reviewer.components.data_table import DataTableWidget
from gui.features.violation_reviewer.components.evidence_viewer import EvidenceViewer

class ReviewerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ReviewerView")
        
        # Khởi tạo 3 mảnh ghép
        self.filter_panel = FilterPanel()
        self.data_table = DataTableWidget()
        self.evidence_viewer = EvidenceViewer()
        
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # 1. Đặt Bộ lọc ở trên cùng
        main_layout.addWidget(self.filter_panel)

        # 2. Đặt Bảng và Khung xem bằng chứng ở dưới
        # Dùng QSplitter để người dùng có thể dùng chuột kéo thay đổi độ rộng giữa Bảng và Ảnh
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.data_table)
        splitter.addWidget(self.evidence_viewer)
        
        # Tỷ lệ chia màn hình: Bảng chiếm 60%, Khung xem chiếm 40%
        splitter.setStretchFactor(0, 6)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter, stretch=1) # stretch=1 để nó đẩy kín không gian trống
# --- END OF FILE ---