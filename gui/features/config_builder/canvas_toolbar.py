# --- START OF FILE gui/features/config_builder/canvas_toolbar.py ---
import os
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSlider, QLabel, QSpacerItem, 
    QSizePolicy, QButtonGroup, QLineEdit, QMenu, QDialog, QVBoxLayout, 
    QCheckBox, QColorDialog, QFormLayout, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QIcon, QColor

from utils.enums import TrafficVehicleType
from infrastructure.visual_annotator import AnnotatorConfig

from gui.shared_components.event_broker import app_broker

class CanvasToolbar(QWidget):
    # Các tín hiệu (Signals) phát ra khi người dùng thao tác
    mode_changed = pyqtSignal(str)   # Gửi chuỗi: 'NONE', 'DRAW', 'ZOOM'
    zoom_changed = pyqtSignal(int)   # Gửi giá trị % zoom (vd: 150)
    toggle_grid = pyqtSignal(bool)   # Bật/tắt lưới
    toggle_fullscreen = pyqtSignal() # Chuyển đổi toàn màn hình
    request_fit_view = pyqtSignal()  

    annotator_config_changed = pyqtSignal(AnnotatorConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setObjectName("BottomToolbar")
        
        # Đường dẫn gốc tới thư mục assets
        self.assets_dir =  os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icons"))
        
        self.current_annotator_config = AnnotatorConfig()

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
        self.btn_grid.setToolTip("Bật/tắt Lớp Đồ họa AI (Chuột PHẢI để tùy chỉnh)")
        self.btn_grid.setCheckable(True)
        self.btn_grid.setChecked(False) 
        
        self.btn_grid.toggled.connect(self._on_grid_toggled)
        
        # Bắt sự kiện click chuột phải để mở Popup (sử dụng customContextMenuRequested)
        self.btn_grid.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.btn_grid.customContextMenuRequested.connect(self._show_annotator_popup)

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
    
    def _show_annotator_popup(self, pos: QPoint):
        """Hiển thị bảng tùy chỉnh khi click chuột phải vào nút Grid"""
        popup = AnnotatorConfigPopup(self.current_annotator_config, self)
        
        # Kết nối tín hiệu khi có thay đổi trong Popup
        popup.config_changed.connect(self._on_annotator_config_updated)
        
        # Tính toán tọa độ để popup hiện ngay trên đỉnh của nút Grid
        global_pos = self.btn_grid.mapToGlobal(QPoint(0, 0))
        # Nâng popup lên trên, bù trừ chiều cao (Khoảng 250px)
        popup.move(global_pos.x(), global_pos.y() - 250) 
        
        popup.exec() # Hiển thị Modal

    def _on_annotator_config_updated(self, new_config: AnnotatorConfig):
        """Cập nhật cấu hình hiện tại và bắn tín hiệu cho Controller"""
        self.current_annotator_config = new_config
        self.annotator_config_changed.emit(new_config)

        app_broker.request_toggle_rois_visibility.emit(new_config.show_rois)    

    def _on_grid_toggled(self, checked: bool):
        self.toggle_grid.emit(checked)

# ==============================================================================
# 2. WIDGET POPUP TÙY CHỈNH CHO VISUAL ANNOTATOR
# ==============================================================================
# --- TRÍCH ĐOẠN CẬP NHẬT POPUP: gui/features/config_builder/canvas_toolbar.py ---

class AnnotatorConfigPopup(QDialog):
    """
    Cửa sổ nhỏ (Popup) hiển thị khi click chuột phải vào nút Grid.
    Cho phép điều chỉnh chi tiết cấu hình của VisualAnnotator.
    """
    config_changed = pyqtSignal(AnnotatorConfig)

    def __init__(self, current_config: AnnotatorConfig, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        
        # [CẬP NHẬT]: Tinh chỉnh CSS để gỡ bỏ nền rác, làm mịn giao diện (Dark theme đồng nhất)
        self.setStyleSheet("""
            QDialog { 
                background-color: #2b2b2b; 
                border: 1px solid #444; 
                border-radius: 5px; 
            }
            QLabel { 
                color: #ffffff; 
                font-weight: bold; 
                background-color: transparent; 
            }
            QCheckBox { 
                color: #e0e0e0; 
                spacing: 8px; 
                background-color: transparent;
            }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QFrame[frameShape="4"] { /* HLine */
                color: #555;
                background-color: #555;
            }
        """)
        
        self.config = current_config 
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # [CẬP NHẬT]: Đổi Tiêu đề
        lbl_title = QLabel("CẤU HÌNH LƯỚI")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

        # 1. Nhóm Bật/Tắt tính năng
        self.chk_show_trails = QCheckBox("Hiển thị quỹ đạo di chuyển")
        self.chk_show_trails.setChecked(self.config.show_trails)
        self.chk_show_trails.toggled.connect(self._on_setting_changed)
        
        self.chk_violators_only = QCheckBox("Chỉ hiển thị xe vi phạm")
        self.chk_violators_only.setChecked(self.config.show_violators_only)
        self.chk_violators_only.setStyleSheet("font-weight: bold;") 
        self.chk_violators_only.toggled.connect(self._on_setting_changed)

        self.chk_show_rois = QCheckBox("Hiển thị Region of Interest (ROIs)")
        self.chk_show_rois.setChecked(self.config.show_rois)
        self.chk_show_rois.setStyleSheet("font-weight: bold;") 
        self.chk_show_rois.toggled.connect(self._on_setting_changed)
        
        layout.addWidget(self.chk_show_trails)
        layout.addWidget(self.chk_violators_only)
        layout.addWidget(self.chk_show_rois)

        # 2. Nhóm Lọc Loại Xe
        layout.addWidget(QLabel("Loại phương tiện:"))
        self.vehicle_checkboxes = {}
        
        grid_vehicles = QHBoxLayout()
        v_types_to_show = [TrafficVehicleType.CAR, TrafficVehicleType.MOTORCYCLE, TrafficVehicleType.TRUCK, TrafficVehicleType.BUS]
        
        for v_type in v_types_to_show:
            chk = QCheckBox(v_type.name)
            chk.setChecked(self.config.visible_classes.get(v_type, True))
            chk.toggled.connect(self._on_setting_changed)
            self.vehicle_checkboxes[v_type] = chk
            grid_vehicles.addWidget(chk)
            
        layout.addLayout(grid_vehicles)

        # 3. Đổi màu trạng thái vi phạm
        layout.addWidget(QLabel("Bảng màu:"))
        form_colors = QFormLayout()
        
        self.btn_color_safe = self._create_color_button(self.config.violation_colors["SAFE"], "SAFE")
        self.btn_color_violating = self._create_color_button(self.config.violation_colors["VIOLATING"], "VIOLATING")
        
        form_colors.addRow("Xe an toàn:", self.btn_color_safe)
        form_colors.addRow("Xe vi phạm:", self.btn_color_violating)
        
        layout.addLayout(form_colors)
    
    def _create_color_button(self, rgb: tuple, state_key: str) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(60, 22)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        
        hex_color = "#{:02x}{:02x}{:02x}".format(*rgb)
        btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #777; border-radius: 3px;")
        
        btn.clicked.connect(lambda: self._choose_color(btn, state_key))
        return btn

    def _choose_color(self, button: QPushButton, state_key: str):
        current_rgb = self.config.violation_colors[state_key]
        initial_color = QColor(current_rgb[0], current_rgb[1], current_rgb[2])
        
        color = QColorDialog.getColor(initial_color, self, f"Chọn màu cho {state_key}")
        
        if color.isValid():
            new_rgb = (color.red(), color.green(), color.blue())
            self.config.violation_colors[state_key] = new_rgb
            
            hex_color = "#{:02x}{:02x}{:02x}".format(*new_rgb)
            button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #777; border-radius: 3px;")
            
            self._on_setting_changed()

    def _on_setting_changed(self):
        self.config.show_trails = self.chk_show_trails.isChecked()
        self.config.show_violators_only = self.chk_violators_only.isChecked()
        self.config.show_rois = self.chk_show_rois.isChecked()
        
        for v_type, chk in self.vehicle_checkboxes.items():
            self.config.visible_classes[v_type] = chk.isChecked()
            
        self.config_changed.emit(self.config)
    

# --- END OF TRÍCH ĐOẠN POPUP ---