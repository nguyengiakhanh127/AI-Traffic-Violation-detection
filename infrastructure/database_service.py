# --- START OF FILE infrastructure/database_service.py (Phiên bản MySQL) ---
import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime

logger = logging.getLogger("DatabaseService")

class DatabaseService:
    def __init__(self, host="localhost", port=3306, user="root", password="", database="traffic_ai_db"):
        self.db_config = {
            "host": host,
            "port": port,         # <--- Bổ sung dòng này
            "user": user,
            "password": password,
            "database": database
        }
        self._init_db()

    def _get_connection(self):
        """Tạo kết nối tới MySQL Server"""
        try:
            return mysql.connector.connect(**self.db_config)
        except Error as e:
            logger.error(f"❌ Không thể kết nối tới MySQL: {e}")
            return None

    def _init_db(self):
        """Tạo bảng chuẩn MySQL (Sử dụng AUTO_INCREMENT thay vì AUTOINCREMENT)"""
        query_cameras = """
        CREATE TABLE IF NOT EXISTS cameras (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            rtsp_url TEXT,
            config_path TEXT,
            route_in VARCHAR(255),
            route_out VARCHAR(255)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        query_violations = """
        CREATE TABLE IF NOT EXISTS violations (
            id INT AUTO_INCREMENT PRIMARY KEY,
            camera_id INT NOT NULL,
            timestamp DATETIME NOT NULL,
            violation_code VARCHAR(100) NOT NULL,
            vehicle_type VARCHAR(100) NOT NULL,
            lane_id VARCHAR(50),
            speed_detected FLOAT,
            speed_min FLOAT,
            speed_max FLOAT,
            license_plate VARCHAR(20) DEFAULT 'Chưa rõ',
            evidence_path TEXT NOT NULL,
            is_reviewed TINYINT(1) DEFAULT 0,
            FOREIGN KEY (camera_id) REFERENCES cameras(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        conn = self._get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(query_cameras)
                cursor.execute(query_violations)
                conn.commit()
                logger.info("✅ Database MySQL đã được khởi tạo thành công.")
            except Error as e:
                logger.error(f"❌ Lỗi tạo bảng MySQL: {e}")
            finally:
                if conn.is_connected():
                    cursor.close()
                    conn.close()

    # ==========================================================
    # QUẢN LÝ CAMERAS
    # ==========================================================
    def add_camera(self, name: str, route_in: str = "", route_out: str = "") -> int:
        conn = self._get_connection()
        if not conn: return -1
        try:
            cursor = conn.cursor()
            # MySQL dùng %s thay cho ?
            cursor.execute("SELECT id FROM cameras WHERE name = %s", (name,))
            existing = cursor.fetchone()
            if existing: return existing[0]
            
            cursor.execute(
                "INSERT INTO cameras (name, route_in, route_out) VALUES (%s, %s, %s)",
                (name, route_in, route_out)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_all_cameras(self) -> list:
        conn = self._get_connection()
        if not conn: return []
        try:
            # dictionary=True giống với sqlite3.Row -> Trả về dữ liệu dạng Dict cho UI dễ xài
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM cameras ORDER BY name")
            return cursor.fetchall()
        finally:
            conn.close()

    def update_camera_config(self, camera_id: int, json_filepath: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE cameras SET config_path = %s WHERE id = %s", (json_filepath, camera_id))
            conn.commit()
            return True
        finally:
            conn.close()

    # ==========================================================
    # QUẢN LÝ VIOLATIONS (BIÊN BẢN VI PHẠM)
    # ==========================================================
    def insert_violation(self, data: dict) -> int:
        conn = self._get_connection()
        if not conn: return -1
        query = """
        INSERT INTO violations (
            camera_id, timestamp, violation_code, vehicle_type, 
            lane_id, speed_detected, speed_min, speed_max, 
            license_plate, evidence_path
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        try:
            cursor = conn.cursor()
            cursor.execute(query, (
                data.get('camera_id'), data.get('timestamp'), data.get('violation_code'),
                data.get('vehicle_type'), data.get('lane_id'), data.get('speed_detected', 0.0),
                data.get('speed_min', 0.0), data.get('speed_max', 0.0),
                data.get('license_plate', 'Chưa rõ'), data.get('evidence_path')
            ))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update_violation_status(self, record_id: int, new_status: int) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE violations SET is_reviewed = %s WHERE id = %s", (new_status, record_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_violations(self, limit: int = 20, offset: int = 0, filters: dict = None) -> list:
        # 1. Rào chắn kết nối ngay dòng đầu tiên
        conn = self._get_connection()
        if not conn: 
            return [] # Thoát ngay và trả về list rỗng nếu không có DB

        query = "SELECT v.*, c.name as camera_name FROM violations v LEFT JOIN cameras c ON v.camera_id = c.id WHERE 1=1"
        params = []
        if filters:
            if filters.get('license_plate'):
                query += " AND license_plate LIKE %s"
                params.append(f"%{filters['license_plate']}%")
            if filters.get('violation_code'):
                query += " AND violation_code = %s"
                params.append(filters['violation_code'])
            if filters.get('vehicle_type'):
                query += " AND vehicle_type = %s"
                params.append(filters['vehicle_type'])
            if filters.get('start_time'):
                query += " AND timestamp >= %s"
                params.append(filters['start_time'])
            if filters.get('end_time'):
                query += " AND timestamp <= %s"
                params.append(filters['end_time'])
            if filters.get('status') is not None:
                query += " AND is_reviewed = %s"
                params.append(filters['status'])

        query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        # 2. Xử lý dữ liệu (Tuyệt đối KHÔNG gán lại biến conn ở đây nữa)
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            return cursor.fetchall()
        except Error as e:
            logger.error(f"❌ Lỗi truy vấn DB: {e}")
            return []
        finally:
            if conn and conn.is_connected():
                conn.close()

    def get_total_count(self, filters: dict = None) -> int:
        # 1. Rào chắn kết nối
        conn = self._get_connection()
        if not conn: 
            return 0 # Trả về 0 nếu không có DB

        query = "SELECT COUNT(id) AS total FROM violations WHERE 1=1"
        params = []
        if filters:
            if filters.get('license_plate'):
                query += " AND license_plate LIKE %s"
                params.append(f"%{filters['license_plate']}%")
            if filters.get('violation_code'):
                query += " AND violation_code = %s"
                params.append(filters['violation_code'])
            if filters.get('vehicle_type'):
                query += " AND vehicle_type = %s"
                params.append(filters['vehicle_type'])
            if filters.get('start_time'):
                query += " AND timestamp >= %s"
                params.append(filters['start_time'])
            if filters.get('end_time'):
                query += " AND timestamp <= %s"
                params.append(filters['end_time'])
            if filters.get('status') is not None:
                query += " AND is_reviewed = %s"
                params.append(filters['status'])

        # 2. Xử lý dữ liệu
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
            return result['total'] if result else 0
        except Error as e:
            logger.error(f"❌ Lỗi đếm DB: {e}")
            return 0
        finally:
            if conn and conn.is_connected():
                conn.close()
# --- END OF FILE ---