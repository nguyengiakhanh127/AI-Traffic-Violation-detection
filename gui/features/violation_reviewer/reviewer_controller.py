# --- START OF FILE gui/features/violation_reviewer/reviewer_controller.py ---

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtWidgets import QMessageBox
import math
import logging

from gui.shared_components.event_broker import app_broker
from infrastructure.database_service import DatabaseService

logger = logging.getLogger("ReviewerController")

class ReviewerController(QObject):
    """
    Trình điều khiển màn hình Quản lý & Xét duyệt Vi phạm (Reviewer).
    Quản lý phân trang, lọc dữ liệu và tương tác an toàn với Cơ sở dữ liệu.
    """
    def __init__(self, view, db_service: DatabaseService):
        super().__init__()
        self.view = view
        self.db = db_service
        
        # Trạng thái Phân trang và Lọc
        self.current_page = 1
        self.items_per_page = 20
        self.current_filters = {} 

        self._wire_signals()
        
        self._load_camera_filter()

        # Nạp dữ liệu lần đầu
        self._fetch_and_update_table()

    def _wire_signals(self) -> None:
        # Lắng nghe từ EventBroker
        app_broker.request_search_violations.connect(self.handle_search)
        app_broker.submit_approval_decision.connect(self.handle_approval_decision)
        app_broker.request_print_ticket.connect(self.handle_print_ticket)
        
        # Nối dây lật trang trực tiếp (do DataTableWidget không bắn qua Broker)
        self.view.data_table.btn_prev.clicked.connect(self.handle_prev_page)
        self.view.data_table.btn_next.clicked.connect(self.handle_next_page)

    @pyqtSlot(dict)
    def handle_search(self, filters: dict) -> None:
        """Xử lý sự kiện khi người dùng bấm nút Tìm kiếm trên Filter Panel"""
        logger.info(f"Yêu cầu lọc dữ liệu: {filters}")
        self.current_filters = filters
        self.current_page = 1 # Reset về trang 1
        self._fetch_and_update_table()

    def handle_prev_page(self) -> None:
        if self.current_page > 1:
            self.current_page -= 1
            self._fetch_and_update_table()

    def handle_next_page(self) -> None:
        # Việc chặn lật lố trang sẽ được kiểm tra ở hàm _fetch
        self.current_page += 1
        self._fetch_and_update_table()

    def _fetch_and_update_table(self) -> None:
        """Kéo dữ liệu từ DB và đẩy lên giao diện an toàn"""
        total_records = self.db.violations.get_total_count(self.current_filters)
        total_pages = math.ceil(total_records / self.items_per_page)
        
        # Kiểm soát ranh giới trang
        if total_pages > 0 and self.current_page > total_pages:
            self.current_page = total_pages
        elif total_pages == 0:
            self.current_page = 1

        if total_records == 0:
            data_list = []
        else:
            offset = max(0, (self.current_page - 1) * self.items_per_page)
            # Gọi an toàn qua lớp con violations của Database Facade
            data_list = self.db.violations.get_list(
                limit=self.items_per_page, 
                offset=offset, 
                filters=self.current_filters
            )

        # Cập nhật UI
        self.view.data_table.load_data(data_list, self.current_page, total_pages)

    @pyqtSlot(str, int)
    def handle_approval_decision(self, record_id: str, new_status: int) -> None:
        """Xử lý Duyệt (1) hoặc Từ chối (-1) biên bản vi phạm"""
        if not record_id: 
            return
        
        success = self.db.violations.update_status(record_id, new_status)
        
        if success:
            # 1. Tự động load lại bảng dữ liệu
            self._fetch_and_update_table()
            
            # 2. Xóa trạng thái của Viewer để tránh bấm nhầm 2 lần
            self.view.evidence_viewer.lbl_details.setText("Xử lý thành công! Vui lòng chọn bản ghi tiếp theo.")
            self.view.evidence_viewer.btn_approve.hide()
            self.view.evidence_viewer.btn_reject.hide()
            
            msg = "Đã DUYỆT biên bản!" if new_status == 1 else "Đã HỦY BỎ bản ghi!"
            logger.info(f"{msg} (ID: {record_id})")
        else:
            QMessageBox.warning(self.view, "Lỗi", "Không thể cập nhật trạng thái vào Cơ sở dữ liệu.")

    @pyqtSlot(str)
    def handle_print_ticket(self, record_id: str) -> None:
        """Chức năng in biên bản (Sẽ phát triển sau)"""
        if not record_id: 
            return
        # Logic In Biên Bản sẽ làm sau (Có thể gọi thư viện docx-template để sinh file Word)
        QMessageBox.information(
            self.view, "Thành công", 
            f"Đang xuất file Biên Bản Phạt Nguội cho ID {record_id}...\n(Tính năng in PDF đang cập nhật)"
        )

    def _load_camera_filter(self) -> None:
        """Lấy danh mục Camera từ CSDL và đẩy xuống View (FilterPanel)"""
        try:
            cameras = self.db.cameras.get_all()
            # Uỷ quyền (delegate) qua View để View gọi Panel
            self.view.filter_panel.load_cameras(cameras)
        except Exception as e:
            logger.error(f"Lỗi khi nạp danh sách camera: {e}")         

# --- END OF FILE gui/features/violation_reviewer/reviewer_controller.py ---