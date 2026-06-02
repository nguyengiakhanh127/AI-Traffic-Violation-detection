# --- START OF FILE gui/features/config_builder/canvas_toolbar.py ---
import os
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSlider, QLabel, QSpacerItem, QSizePolicy, QButtonGroup, QLineEdit, QMenu
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

class CanvasToolbar(QWidget):
    # Các tín hiệu (Signals) phát ra khi người dùng thao tác
    mode_changed = pyqtSignal(str)   # Gửi chuỗi: 'NONE', 'DRAW', 'ZOOM'
    zoom_changed = pyqtSignal(int)   # Gửi giá trị % zoom (vd: 150)
    toggle_grid = pyqtSignal(bool)   # Bật/tắt lưới
    toggle_fullscreen = pyqtSignal() # Chuyển đổi toàn màn hình
    request_fit_view = pyqtSignal()  
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setObjectName("BottomToolbar")
        
        # Đường dẫn gốc tới thư mục assets
        self.assets_dir =  os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons"))
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)

        # 1. NHÓM NÚT CÔNG CỤ (Tool Buttons)
        # Sử dụng QButtonGroup để đảm bảo chỉ 1 nút được bật (Checked) tại 1 thời điểm
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(False) # Tắt exclusive để cho phép tắt hẳn nút (bỏ chọn)
        
        # Nút Vẽ (Bút chì)
        self.btn_draw = QPushButton()
        self.btn_draw.setIcon(QIcon(os.path.join(self.assets_dir, "pencil.png")))
        self.btn_draw.setToolTip("Công cụ Vẽ ROI")
        
        # Tạo Popup Menu cho nút Bút chì
        draw_menu = QMenu(self)
        draw_menu.addAction("Vẽ Đa giác (Polygon)", lambda: self._emit_draw_mode("DRAW_POLYGON"))
        draw_menu.addAction("Vẽ Hộp (BBox)", lambda: self._emit_draw_mode("DRAW_BBOX"))
        draw_menu.addAction("Vẽ Đoạn thẳng (Line)", lambda: self._emit_draw_mode("DRAW_LINE"))
        
        # Gắn menu vào nút (PyQt sẽ hiển thị mũi tên xổ xuống nhỏ bên cạnh icon)
        self.btn_draw.setMenu(draw_menu)

        # Nút Kính lúp (Zoom)
        self.btn_zoom = self._create_tool_button("zoom.png", "Kính lúp (Zoom)", "ZOOM")
        
        # 2. NHÓM NÚT TIỆN ÍCH (Utility Buttons)
        self.btn_fullscreen = QPushButton()
        self.btn_fullscreen.setIcon(QIcon(os.path.join(self.assets_dir, "fullscreen.png")))
        print(QIcon(os.path.join(self.assets_dir, "fullscreen.png")))
        self.btn_fullscreen.setToolTip("Toàn màn hình")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen.emit)
        
        self.btn_grid = QPushButton()
        self.btn_grid.setIcon(QIcon(os.path.join(self.assets_dir, "grid.png")))
        self.btn_grid.setToolTip("Bật/tắt lưới")
        self.btn_grid.setCheckable(True)
        self.btn_grid.toggled.connect(self.toggle_grid.emit)

        # 3. THANH TRƯỢT ZOOM (Zoom Slider)
        self.slider_zoom = QSlider(Qt.Orientation.Horizontal)
        self.slider_zoom.setRange(10, 500) 
        self.slider_zoom.setValue(100)     
        self.slider_zoom.setFixedWidth(150)
        self.slider_zoom.valueChanged.connect(self._on_slider_moved)
        
        # [CẬP NHẬT]: Đổi QLabel thành QLineEdit cho phép nhập tay
        self.input_zoom_val = QLineEdit("100%")
        self.input_zoom_val.setFixedWidth(50)
        self.input_zoom_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_zoom_val.setStyleSheet("background-color: #333; color: white; border: 1px solid #555; border-radius: 2px;")
        
        self.btn_fit_view = QPushButton()
        # Dùng một Icon có sẵn hoặc chữ cho nhanh:
        self.btn_fit_view.setIcon(QIcon(os.path.join(self.assets_dir, "fit_to_screen_2.png")))
        self.btn_fit_view.setToolTip("Đưa ảnh về trung tâm và thu phóng vừa màn hình (Fit to Window)")
        
        # Bắt sự kiện bắn ra một Signal (Sẽ kết nối vào Canvas sau)
        self.btn_fit_view.clicked.connect(self.request_fit_view.emit)

        # Bắt sự kiện khi người dùng gõ xong và bấm phím Enter
        self.input_zoom_val.returnPressed.connect(self._on_zoom_input_entered)

        # Sắp xếp bố cục (Thêm Spacer để dồn thanh Zoom về bên phải)
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout.addWidget(self.btn_draw)
        layout.addWidget(self.btn_zoom)
        layout.addWidget(self.btn_fullscreen)
        layout.addWidget(self.btn_grid)
        layout.addSpacerItem(spacer)
        layout.addWidget(QLabel("Zoom:"))
        layout.addWidget(self.slider_zoom)
        layout.addWidget(self.input_zoom_val)
        layout.addWidget(self.btn_fit_view)

        # Bắt sự kiện khi một nút công cụ được bấm
        self.tool_group.buttonToggled.connect(self._on_tool_toggled)

    def _create_tool_button(self, icon_name: str, tooltip: str, mode_name: str) -> QPushButton:
        """Hàm hỗ trợ tạo nút công cụ có tính chất Bật/Tắt"""
        btn = QPushButton()
        icon_path = os.path.join(self.assets_dir, icon_name)
        btn.setIcon(QIcon(icon_path))
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        # Gán tên Mode cho nút để dễ phân biệt
        btn.setProperty("mode_name", mode_name)
        self.tool_group.addButton(btn)
        return btn

    def _on_tool_toggled(self, button: QPushButton, checked: bool):
        """Xử lý khi bật/tắt nút công cụ (Đảm bảo chỉ 1 nút bật)"""
        if checked:
            # Tắt các nút khác trong nhóm
            for btn in self.tool_group.buttons():
                if btn != button and btn.isChecked():
                    btn.blockSignals(True)
                    btn.setChecked(False)
                    btn.blockSignals(False)
            
            # Gửi tín hiệu trạng thái mới
            mode = button.property("mode_name")
            self.mode_changed.emit(mode)
        else:
            # Nếu người dùng bấm tắt chính nút đó -> Trở về trạng thái mặc định (NONE)
            self.mode_changed.emit("NONE")

    def _on_slider_moved(self, value: int):
        # Tự động cập nhật số trong hộp text khi kéo thanh trượt
        self.input_zoom_val.setText(f"{value}%")
        self.zoom_changed.emit(value)

    def update_zoom_from_canvas(self, value: int):
        """Hàm này được Canvas gọi khi lăn chuột, giúp Slider chạy theo con lăn"""
        self.slider_zoom.blockSignals(True) # Chặn signal để tránh vòng lặp vô tận (Infinite Loop)
        
        self.slider_zoom.setValue(value)
        
        # [QUAN TRỌNG]: Cập nhật con số hiển thị trong khung nhập text (QLineEdit)
        self.input_zoom_val.setText(f"{value}%") 
        
        self.slider_zoom.blockSignals(False)

    def _on_zoom_input_entered(self):
        text = self.input_zoom_val.text().replace("%", "").strip()
        try:
            val = int(text)
            # Khóa giá trị trong khoảng an toàn 10% - 500%
            val = max(10, min(500, val))
            # Gán vào slider (Slider sẽ tự động gọi _on_slider_moved để báo cho Canvas)
            self.slider_zoom.setValue(val)
        except ValueError:
            # Nếu người dùng nhập linh tinh (chữ cái), khôi phục lại giá trị cũ
            self.input_zoom_val.setText(f"{self.slider_zoom.value()}%")
            
    def _emit_draw_mode(self, mode_str: str):
        # Tắt các nút khác để giữ đồng bộ UI
        for btn in self.tool_group.buttons():
            btn.setChecked(False)
        self.mode_changed.emit(mode_str)
# --- END OF FILE gui/features/config_builder/canvas_toolbar.py ---