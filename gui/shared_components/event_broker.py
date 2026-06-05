# --- START OF FILE gui/shared_components/event_broker.py ---

from PyQt6.QtCore import QObject, pyqtSignal

class EventBroker(QObject):
    """
    Hệ thống thông báo trung tâm (Message Broker) dựa trên tín hiệu Qt.
    Đảm bảo việc truyền dữ liệu giữa các luồng (Core <-> GUI) diễn ra an toàn.
    """
    
    # 1. Các tín hiệu vẽ và tương tác của Config Builder
    request_draw_polygon = pyqtSignal(object)   
    request_draw_bbox = pyqtSignal(object)      
    request_draw_line = pyqtSignal(object, str) 

    # 2. Các tín hiệu Đồ họa & UI
    request_highlight_polygon = pyqtSignal(str)
    clear_highlight_polygon = pyqtSignal()

    request_highlight_sub_edge = pyqtSignal(str, int)
    clear_highlight_sub_edge = pyqtSignal(str, int)

    request_edge_count = pyqtSignal(object, str) 

    request_delete_entity = pyqtSignal(str)

    request_toggle_rois_visibility = pyqtSignal(bool)

    # 3. Các tín hiệu dữ liệu Cấu hình
    # rule_updated(đối tượng rule, lane_id, rule_type, allowed_vehicles)
    rule_updated = pyqtSignal(object, str, str, set) 
    
    # ====================================================================
    # 4. Các tín hiệu cho màn hình Kiểm duyệt (Reviewer/DB)
    # ====================================================================
    request_search_violations = pyqtSignal(dict) # Từ điển bộ lọc
    violation_row_selected = pyqtSignal(dict)    # Từ điển dữ liệu hàng

    submit_approval_decision = pyqtSignal(str, int) # Record_ID (str/MongoDB ObjectId), Quyết định
    request_print_ticket = pyqtSignal(str)          # Record_ID (str/MongoDB ObjectId)
    toggle_db_logging = pyqtSignal(bool)            # Bật/Tắt Ghi DB
    
app_broker = EventBroker()

# --- END OF FILE gui/shared_components/event_broker.py ---