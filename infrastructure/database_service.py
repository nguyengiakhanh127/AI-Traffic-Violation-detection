# --- START OF FILE infrastructure/database_service.py ---

import logging
import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
from typing import List, Dict, Optional, Any

logger = logging.getLogger("DatabaseService")

class CameraRepository:
    """
    Xử lý các thao tác CSDL liên quan đến danh mục Camera.
    Sử dụng Connection Pool được tiêm từ DatabaseService.
    """
    def __init__(self, pool: MySQLConnectionPool):
        self.pool = pool

    def add(self, ten_camera: str, tuyen_vao: str = "", tuyen_ra: str = "") -> int:
        query_check = "SELECT id FROM danh_muc_camera WHERE ten_camera = %s"
        query_insert = "INSERT INTO danh_muc_camera (ten_camera, tuyen_duong_vao, tuyen_duong_ra) VALUES (%s, %s, %s)"
        
        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query_check, (ten_camera,))
            existing = cursor.fetchone()
            if existing: 
                return existing[0]
            
            cursor.execute(query_insert, (ten_camera, tuyen_vao, tuyen_ra))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_all(self) -> List[Dict[str, Any]]:
        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM danh_muc_camera ORDER BY ten_camera")
            return cursor.fetchall()
        finally:
            conn.close()

    def update_config_path(self, camera_id: int, file_path: str) -> bool:
        query = "UPDATE danh_muc_camera SET duong_dan_cau_hinh = %s WHERE id = %s"
        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (file_path, camera_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

class ViolationRepository:
    """
    Xử lý các thao tác CSDL liên quan đến hồ sơ vi phạm.
    Được thiết kế an toàn luồng (Thread-safe) nhờ Connection Pool.
    """
    def __init__(self, pool: MySQLConnectionPool):
        self.pool = pool

    def insert(self, camera_id: int, thoi_gian: str, ma_loi: str, loai_xe: str, 
               lan_duong: str, duong_dan: str, bien_so: str = "Chưa rõ") -> int:
        query = """
        INSERT INTO ho_so_vi_pham (
            camera_id, thoi_gian_vi_pham, ma_loi_vi_pham, loai_phuong_tien, 
            lan_duong, bien_so_xe, duong_dan_bang_chung
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query, (
                camera_id, thoi_gian, ma_loi, loai_xe, lan_duong, bien_so, duong_dan
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_status(self, record_id: int, trang_thai: int) -> bool:
        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE ho_so_vi_pham SET trang_thai_duyet = %s WHERE id = %s", (trang_thai, record_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_list(self, limit: int = 20, offset: int = 0, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        query = """
        SELECT v.*, c.ten_camera 
        FROM ho_so_vi_pham v 
        LEFT JOIN danh_muc_camera c ON v.camera_id = c.id 
        WHERE 1=1
        """
        params: List[Any] = []
        
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
            # [THÊM MỚI]: Bắt điều kiện Camera ID
            if filters.get('camera_id') is not None:
                query += " AND camera_id = %s"
                params.append(filters['camera_id'])

        query += " ORDER BY thoi_gian_vi_pham DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
        finally:
            conn.close()    
    
    def get_total_count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        query = "SELECT COUNT(id) AS total FROM ho_so_vi_pham WHERE 1=1"
        params: List[Any] = []
        
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
            # [THÊM MỚI]: Bắt điều kiện Camera ID
            if filters.get('camera_id') is not None:
                query += " AND camera_id = %s"
                params.append(filters['camera_id'])

        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
            return result['total'] if result else 0
        finally:
            conn.close()
        
    def update_license_plate(self, record_id: int, bien_so: str) -> bool:
        conn = self.pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE ho_so_vi_pham SET bien_so_xe = %s WHERE id = %s", (bien_so, record_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

class DatabaseService:
    """
    Facade chịu trách nhiệm khởi tạo Connection Pool và điều phối các Repositories.
    Chỉ khởi tạo 1 lần duy nhất khi ứng dụng bắt đầu.
    """
    def __init__(self, host: str = "localhost", port: int = 3306, user: str = "root", 
                 password: str = "", database: str = "traffic_ai_db", pool_size: int = 5):
        try:
            self.db_pool = MySQLConnectionPool(
                pool_name="traffic_ai_pool",
                pool_size=pool_size,
                host=host,
                port=port,
                user=user,
                password=password,
                database=database
            )
            logger.info("✅ Đã khởi tạo thành công Database Connection Pool.")
        except Error as e:
            logger.error(f"❌ Không thể tạo Connection Pool: {e}")
            raise e
        
        self.cameras = CameraRepository(self.db_pool)
        self.violations = ViolationRepository(self.db_pool)
        
        self._init_schema()

    def _init_schema(self) -> None:
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
        conn = self.db_pool.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(query_cameras)
            cursor.execute(query_violations)
            conn.commit()
        except Error as e:
            logger.error(f"❌ Lỗi khởi tạo Database Schema: {e}")
        finally:
            conn.close()

# --- END OF FILE infrastructure/database_service.py ---