# --- START OF FILE gui/features/violation_reviewer/reviewer_controller.py ---
from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
import math
from gui.shared_components.event_broker import app_broker
from infrastructure.database_service import DatabaseService

class ReviewerController(QObject):
    def __init__(self, view, db_service: DatabaseService):
        super().__init__()
        self.view = view
        self.db = db_service
        
        # Trạng thái Phân trang và Lọc
        self.current_page = 1
        self.items_per_page = 20
        self.current_filters = {} # Lưu lại bộ lọc để khi lật trang không bị mất điều kiện tìm kiếm

        self._wire_signals()
        
        # Lần đầu bật màn hình lên -> Tự động load trang 1
        self._fetch_and_update_table()

    def _wire_signals(self):
        # 1. Lắng nghe yêu cầu tìm kiếm từ EventBroker (Do Filter Panel phát ra)
        app_broker.request_search_violations.connect(self.handle_search)
        
        # 2. Nối dây nút bấm lật trang của Bảng dữ liệu
        self.view.data_table.btn_prev.clicked.connect(self.handle_prev_page)
        self.view.data_table.btn_next.clicked.connect(self.handle_next_page)

        app_broker.submit_approval_decision.connect(self.handle_approval_decision)
        app_broker.request_print_ticket.connect(self.handle_print_ticket)

    @pyqtSlot(dict)
    def handle_search(self, filters: dict):
        """Khi người dùng bấm nút Tìm kiếm"""
        print(f"[REVIEWER] Nhận yêu cầu tìm kiếm: {filters}")
        self.current_filters = filters
        self.current_page = 1 # Tìm kiếm mới thì luôn quay về trang 1
        self._fetch_and_update_table()

    def handle_prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._fetch_and_update_table()

    def handle_next_page(self):
        # Sẽ kiểm tra chặn không cho lật lố trang max bên trong hàm _fetch
        self.current_page += 1
        self._fetch_and_update_table()

    def _fetch_and_update_table(self):
        # 1. Gọi vào Repository (Thêm '.violations.')
        total_records = self.db.violations.get_total_count(self.current_filters)
        total_pages = math.ceil(total_records / self.items_per_page)
        
        if total_pages > 0 and self.current_page > total_pages:
            self.current_page = total_pages
        elif total_pages == 0:
            self.current_page = 1

        if total_records == 0:
            data_list = []
        else:
            offset = max(0, (self.current_page - 1) * self.items_per_page)
            # 2. Gọi vào Repository (Thêm '.violations.')
            data_list = self.db.violations.get_list(
                limit=self.items_per_page, 
                offset=offset, 
                filters=self.current_filters
            )

        self.view.data_table.load_data(data_list, self.current_page, total_pages)

    @pyqtSlot(int, int)
    def handle_approval_decision(self, record_id: int, new_status: int):
        if not record_id: return
        
        # Gọi Database cập nhật
        success = self.db.update_violation_status(record_id, new_status)
        
        if success:
            # 1. Tự động load lại cái Bảng (dòng vừa duyệt sẽ tự động biến mất nếu đang lọc 'Chờ duyệt')
            self._fetch_and_update_table()
            
            # 2. Xóa trắng thông tin trên Evidence Viewer đi để tránh người dùng bấm 2 lần
            self.view.evidence_viewer.lbl_details.setText("Xử lý thành công! Vui lòng chọn bản ghi tiếp theo.")
            self.view.evidence_viewer.btn_approve.hide()
            self.view.evidence_viewer.btn_reject.hide()
            
            # 3. Hiện thông báo nhỏ (Tùy chọn)
            msg = "Đã DUYỆT biên bản!" if new_status == 1 else "Đã HỦY BỎ bản ghi!"
            print(f"[REVIEWER] {msg} (ID: {record_id})")

    @pyqtSlot(int)
    def handle_print_ticket(self, record_id: int):
        if not record_id: return
        # Logic In Biên Bản sẽ làm sau (Có thể gọi thư viện docx-template để sinh file Word)
        QMessageBox.information(self.view, "Thành công", f"Đang xuất file Biên Bản Phạt Nguội cho ID {record_id}...\n(Tính năng in PDF đang cập nhật)")

# --- END OF FILE ---