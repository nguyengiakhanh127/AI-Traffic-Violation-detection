# --- MỞ TỆP: gui/shared_components/event_broker.py ---
from PyQt6.QtCore import QObject, pyqtSignal

class EventBroker(QObject):
    # 1. Các tín hiệu vẽ của Config Builder
    request_draw_polygon = pyqtSignal(object)
    request_draw_bbox = pyqtSignal(object)
    request_draw_line = pyqtSignal(object, str)

    # 2. Các tín hiệu Đồ họa
    request_highlight_polygon = pyqtSignal(str)
    clear_highlight_polygon = pyqtSignal()
    request_edge_count = pyqtSignal(object, str)
    request_highlight_sub_edge = pyqtSignal(str, int)
    clear_highlight_sub_edge = pyqtSignal(str, int)

    # 3. Các tín hiệu dữ liệu Config
    rule_updated = pyqtSignal(object, str, str, set)
    
    # ====================================================================
    # 4. CÁC TÍN HIỆU MỚI THÊM CHO MÀN HÌNH KIỂM DUYỆT (REVIEWER)
    # (ĐẢM BẢO BẠN CÓ 2 DÒNG NÀY TRONG FILE NHÉ)
    # ====================================================================
    request_search_violations = pyqtSignal(dict) # Phát ra khi ấn Tìm kiếm
    violation_row_selected = pyqtSignal(dict)    # Phát ra khi Click vào Bảng

    submit_approval_decision = pyqtSignal(int, int) 
    request_print_ticket = pyqtSignal(int)  
    toggle_db_logging = pyqtSignal(bool)
    
app_broker = EventBroker()