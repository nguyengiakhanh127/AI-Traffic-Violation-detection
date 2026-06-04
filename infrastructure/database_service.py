import mysql.connector
from mysql.connector import Error
import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger("DatabaseService")

# ==========================================================
# 1. TRÌNH QUẢN LÝ KẾT NỐI (CONTEXT MANAGER)
# Giúp loại bỏ hoàn toàn các khối try...finally lặp đi lặp lại
# ==========================================================
class DBConnection:
    """Tự động mở và đóng kết nối an toàn bằng lệnh 'with'"""
    def __init__(self, config: dict):
        self.config = config
        self.conn = None
        
    def __enter__(self):
        try:
            self.conn = mysql.connector.connect(**self.config)
            return self.conn
        except Error as e:
            logger.error(f"❌ Không thể kết nối tới MySQL: {e}")
            raise e
            
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn and self.conn.is_connected():
            self.conn.close()


# ==========================================================
# 2. REPOSITORIES (LỚP XỬ LÝ TRUY VẤN RIÊNG BIỆT)
# ==========================================================

class CameraRepository:
    def __init__(self, db_config: dict):
        self.db_config = db_config

    def add(self, ten_camera: str, tuyen_vao: str = "", tuyen_ra: str = "") -> int:
        query_check = "SELECT id FROM danh_muc_camera WHERE ten_camera = %s"
        query_insert = "INSERT INTO danh_muc_camera (ten_camera, tuyen_duong_vao, tuyen_duong_ra) VALUES (%s, %s, %s)"
        
        with DBConnection(self.db_config) as conn:
            cursor = conn.cursor()
            cursor.execute(query_check, (ten_camera,))
            existing = cursor.fetchone()
            if existing: return existing[0]
            
            cursor.execute(query_insert, (ten_camera, tuyen_vao, tuyen_ra))
            conn.commit()
            return cursor.lastrowid

    def get_all(self) -> List[Dict]:
        with DBConnection(self.db_config) as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM danh_muc_camera ORDER BY ten_camera")
            return cursor.fetchall()

    def update_config_path(self, camera_id: int, file_path: str) -> bool:
        """[HÀM BỔ SUNG]: Gắn file JSON cấu hình vào Camera"""
        from infrastructure.database_service import DBConnection # Đảm bảo đã import
        query = "UPDATE danh_muc_camera SET duong_dan_cau_hinh = %s WHERE id = %s"
        with DBConnection(self.db_config) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (file_path, camera_id))
            conn.commit()
            return cursor.rowcount > 0

class ViolationRepository:
    def __init__(self, db_config: dict):
        self.db_config = db_config

    def insert(self, camera_id: int, thoi_gian: str, ma_loi: str, loai_xe: str, 
               lan_duong: str, duong_dan: str, bien_so: str = "Chưa rõ") -> int:
        query = """
        INSERT INTO ho_so_vi_pham (
            camera_id, thoi_gian_vi_pham, ma_loi_vi_pham, loai_phuong_tien, 
            lan_duong, bien_so_xe, duong_dan_bang_chung
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with DBConnection(self.db_config) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                camera_id, thoi_gian, ma_loi, loai_xe, lan_duong, bien_so, duong_dan
            ))
            conn.commit()
            return cursor.lastrowid

    def update_status(self, record_id: int, trang_thai: int) -> bool:
        with DBConnection(self.db_config) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE ho_so_vi_pham SET trang_thai_duyet = %s WHERE id = %s", (trang_thai, record_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_list(self, limit: int = 20, offset: int = 0, filters: dict = None) -> List[Dict]:
        query = """
        SELECT v.*, c.ten_camera 
        FROM ho_so_vi_pham v 
        LEFT JOIN danh_muc_camera c ON v.camera_id = c.id 
        WHERE 1=1
        """
        params = []
        
        # Xây dựng câu truy vấn động dựa trên bộ lọc
        if filters:
            if filters.get('bien_so'):
                query += " AND bien_so_xe LIKE %s"
                params.append(f"%{filters['bien_so']}%")
            if filters.get('ma_loi'):
                query += " AND ma_loi_vi_pham = %s"
                params.append(filters['ma_loi'])
            if filters.get('loai_xe'):
                query += " AND loai_phuong_tien = %s"
                params.append(filters['loai_xe'])
            if filters.get('trang_thai') is not None:
                query += " AND trang_thai_duyet = %s"
                params.append(filters['trang_thai'])

        query += " ORDER BY thoi_gian_vi_pham DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with DBConnection(self.db_config) as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
    
    def get_total_count(self, filters: dict = None) -> int:
        """Đếm tổng số bản ghi (Dùng để tính số trang trong Reviewer Controller)"""
        from infrastructure.database_service import DBConnection # Đảm bảo import an toàn
        
        query = "SELECT COUNT(id) AS total FROM ho_so_vi_pham WHERE 1=1"
        params = []
        
        # Xây dựng bộ lọc y hệt như hàm get_list
        if filters:
            if filters.get('bien_so'):
                query += " AND bien_so_xe LIKE %s"
                params.append(f"%{filters['bien_so']}%")
            if filters.get('ma_loi'):
                query += " AND ma_loi_vi_pham = %s"
                params.append(filters['ma_loi'])
            if filters.get('loai_xe'):
                query += " AND loai_phuong_tien = %s"
                params.append(filters['loai_xe'])
            if filters.get('start_time'):
                query += " AND thoi_gian_vi_pham >= %s"
                params.append(filters['start_time'])
            if filters.get('end_time'):
                query += " AND thoi_gian_vi_pham <= %s"
                params.append(filters['end_time'])
            if filters.get('trang_thai') is not None:
                query += " AND trang_thai_duyet = %s"
                params.append(filters['trang_thai'])

        try:
            with DBConnection(self.db_config) as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute(query, tuple(params))
                result = cursor.fetchone()
                return result['total'] if result else 0
        except Exception as e:
            import logging
            logging.getLogger("DatabaseService").error(f"❌ Lỗi đếm tổng DB: {e}")
            return 0
        
    def update_license_plate(self, record_id: int, bien_so: str) -> bool:
        """Cập nhật biển số xe sau khi OCR chạy xong dưới nền"""
        from infrastructure.database_service import DBConnection
        with DBConnection(self.db_config) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE ho_so_vi_pham SET bien_so_xe = %s WHERE id = %s", (bien_so, record_id))
            conn.commit()
            return cursor.rowcount > 0


# ==========================================================
# 3. FACADE SERVICE (Mặt tiền Giao tiếp)
# ==========================================================

class DatabaseService:
    def __init__(self, host="localhost", port=3306, user="root", password="", database="traffic_ai_db"):
        self.db_config = {
            "host": host, "port": port, "user": user, 
            "password": password, "database": database
        }
        
        # Khởi tạo các Repository con
        self.cameras = CameraRepository(self.db_config)
        self.violations = ViolationRepository(self.db_config)
        
        # Tự động tạo bảng nếu chưa có
        self._init_schema()

    def _init_schema(self):
        """Khởi tạo cấu trúc CSDL bằng Tiếng Việt"""
        query_cameras = """
        CREATE TABLE IF NOT EXISTS danh_muc_camera (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ten_camera VARCHAR(255) UNIQUE NOT NULL,
            link_rtsp TEXT,
            duong_dan_cau_hinh TEXT,
            tuyen_duong_vao VARCHAR(255),
            tuyen_duong_ra VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        query_violations = """
        CREATE TABLE IF NOT EXISTS ho_so_vi_pham (
            id INT AUTO_INCREMENT PRIMARY KEY,
            camera_id INT NOT NULL,
            thoi_gian_vi_pham DATETIME NOT NULL,
            ma_loi_vi_pham VARCHAR(100) NOT NULL,
            loai_phuong_tien VARCHAR(100) NOT NULL,
            lan_duong VARCHAR(50),
            bien_so_xe VARCHAR(20) DEFAULT 'Chưa rõ',
            duong_dan_bang_chung TEXT NOT NULL,
            trang_thai_duyet TINYINT(1) DEFAULT 0,
            FOREIGN KEY (camera_id) REFERENCES danh_muc_camera(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        try:
            with DBConnection(self.db_config) as conn:
                cursor = conn.cursor()
                cursor.execute(query_cameras)
                cursor.execute(query_violations)
                conn.commit()
                logger.info("✅ Database MySQL (Tiếng Việt) đã được khởi tạo.")
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo Database Schema: {e}")