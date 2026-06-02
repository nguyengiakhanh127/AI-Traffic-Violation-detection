# --- START UPDATE: gui/shared_components/reference_combobox.py ---
from PyQt6.QtWidgets import QComboBox, QAbstractItemView # [CẬP NHẬT: Import lớp QAbstractItemView]
from PyQt6.QtCore import pyqtSignal, QEvent, QObject

class HoverEventFilter(QObject):
    item_hovered = pyqtSignal(int)
    menu_hidden = pyqtSignal()

    # [CẬP NHẬT: Nhận thêm tham chiếu đến list_view gốc để luôn gọi indexAt an toàn]
    def __init__(self, list_view: QAbstractItemView, parent=None):
        super().__init__(parent)
        self.list_view = list_view 

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove:
            # 1. Tính toán tọa độ chuột tương đối so với list_view gốc
            # Vì event.pos() có thể so với viewport, ta cần map nó về tọa độ view chuẩn
            pos = event.pos()
            if obj != self.list_view:
                # Nếu event phát ra từ viewport, map nó về tọa độ của list_view
                pos = self.list_view.viewport().mapTo(self.list_view, pos)
                
            # 2. Gọi indexAt từ list_view gốc (Chắc chắn 100% có hàm này)
            index = self.list_view.indexAt(pos)
            if index.isValid():
                self.item_hovered.emit(index.row())
                
        elif event.type() == QEvent.Type.Hide:
            self.menu_hidden.emit()
            
        return super().eventFilter(obj, event)

class ReferenceComboBox(QComboBox):
    reference_hovered = pyqtSignal(str)
    reference_cleared = pyqtSignal()

    def __init__(self, target_type="POLYGONS", allow_manual=False, parent=None): # Thêm cờ allow_manual mặc định là False
        super().__init__(parent)
        self.target_type = target_type
        self.allow_manual = allow_manual
        
        self.setStyleSheet("background-color: #1e1e1e; border: 1px solid #444; padding: 4px;")
        
        # Chỉ thêm nút Vẽ thủ công nếu được cho phép
        if self.allow_manual:
            self.addItem("✏ Tạo thủ công (Draw New)")

        self.view().setMouseTracking(True)
        self.view().viewport().setMouseTracking(True)

        self.hover_filter = HoverEventFilter(self.view(), self)
        self.view().viewport().installEventFilter(self.hover_filter)
        self.view().installEventFilter(self.hover_filter)

        self.hover_filter.item_hovered.connect(self._on_item_hovered)
        self.hover_filter.menu_hidden.connect(self.reference_cleared.emit)

    def _on_item_hovered(self, row: int):
        text = self.itemText(row)
        if text not in ["✏ Tạo thủ công (Draw New)", "Trống"]: # Chặn không highlight nếu rê vào chữ Trống
            self.reference_hovered.emit(text)
        else:
            self.reference_cleared.emit()

    def update_registry(self, registry_data: dict):
        """[CẬP NHẬT]: Tự động hiển thị Trống nếu không có dữ liệu"""
        current_text = self.currentText() 
        self.clear()
        
        keys_list = registry_data.get(self.target_type, [])
        
        # Nếu tủ dữ liệu trống -> Hiển thị "Trống" và Khóa ComboBox
        if not keys_list and not self.allow_manual:
            self.addItem("Trống")
            self.setEnabled(False)
            return
            
        self.setEnabled(True)
        if self.allow_manual:
            self.addItem("✏ Tạo thủ công (Draw New)")
            
        self.addItems(keys_list)
        
        idx = self.findText(current_text)
        if idx >= 0:
            self.setCurrentIndex(idx)

# --- END UPDATE ---