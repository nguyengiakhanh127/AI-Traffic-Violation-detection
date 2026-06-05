# --- START OF FILE infrastructure/evidence_generator.py ---

import cv2
import numpy as np
import os
import logging
import threading
from queue import Queue, Full
from typing import List, Tuple, Optional
from dataclasses import dataclass
from geometry.primitives import Vertex

logger = logging.getLogger("EvidenceGen")

@dataclass
class ImageExportTask:
    """Cấu trúc dữ liệu chứa nhiệm vụ ghi ảnh xuống đĩa"""
    filepath: str
    image_data: np.ndarray

class EvidenceGenerator:
    """
    Trình sinh bằng chứng không đồng bộ (Asynchronous).
    Xử lý xử lý đồ họa trên CPU và đẩy việc ghi I/O sang một luồng ngầm định
    để không chặn (block) vòng lặp phát hiện của AI.
    """
    def __init__(self, queue_size: int = 100):
        self._export_queue: Queue[ImageExportTask] = Queue(maxsize=queue_size)
        self._is_running: bool = True
        
        self._worker_thread = threading.Thread(
            target=self._async_export_worker,
            name="ImageExportWorker",
            daemon=True
        )
        self._worker_thread.start()

    def shutdown(self) -> None:
        """Đóng luồng ghi ảnh an toàn"""
        self._is_running = False
        self._export_queue.put(None) # Poison pill
        self._worker_thread.join(timeout=2.0)
        logger.info("Luồng xuất ảnh đã đóng an toàn.")

    def _async_export_worker(self) -> None:
        """Worker chạy nền, liên tục lấy ảnh từ hàng đợi để ghi ra ổ cứng"""
        while self._is_running:
            task = self._export_queue.get()
            if task is None: 
                break # Tín hiệu dừng
                
            try:
                cv2.imwrite(task.filepath, task.image_data)
            except Exception as e:
                logger.error(f"❌ Lỗi ghi ảnh bằng chứng ({task.filepath}): {e}")
            finally:
                self._export_queue.task_done()

    @staticmethod
    def draw_violation_highlight(
        base_image: np.ndarray, 
        target_bbox: Tuple[int, int, int, int], 
        trajectory: List[Vertex]
    ) -> Optional[np.ndarray]:
        if base_image is None or target_bbox is None:
            return None
            
        img = base_image.copy()
        x1, y1, x2, y2 = target_bbox
        
        h, w = img.shape[:2]
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w, int(x2)), min(h, int(y2))
        
        color_bbox = (0, 255, 0)
        cv2.rectangle(img, (x1, y1), (x2, y2), color_bbox, 2)
        
        color_target = (0, 0, 255)
        cv2.circle(img, (x2, y1), 8, color_target, -1)
        
        if trajectory and len(trajectory) >= 2:
            pts = np.array([[int(v.x), int(v.y)] for v in trajectory], np.int32)
            pts = pts.reshape((-1, 1, 2))
            
            cv2.polylines(img, [pts], isClosed=False, color=color_target, thickness=2)
            
            for pt in trajectory:
                cv2.circle(img, (int(pt.x), int(pt.y)), 4, color_target, -1)
                
        return img

    @staticmethod
    def crop_vehicle(base_image: np.ndarray, bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        if base_image is None or bbox is None:
            return None
            
        x1, y1, x2, y2 = bbox
        h, w = base_image.shape[:2]
        
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w, int(x2)), min(h, int(y2))
        
        return base_image[y1:y2, x1:x2]

    def export_evidence_images(
        self,
        vehicle, 
        violation_code: str, 
        img_dir: str, 
        timestamp_str: str
    ) -> None:
        """
        Thu thập ảnh vi phạm, xử lý đồ họa (highlight) và đẩy vào hàng đợi xuất ảnh.
        Hàm này trả về ngay lập tức (Non-blocking).
        """
        try:
            f_frame = vehicle.get_first_frame()
            f_bbox = vehicle.first_bbox
            l_frame = vehicle.get_violation_frame(violation_code)
            l_bbox = vehicle.violation_bboxes.get(violation_code)
            
            trajectory = list(vehicle.coordinate.trajectory) if vehicle.coordinate else []
            tasks: List[ImageExportTask] = []
            
            if f_frame is not None and f_bbox is not None:
                img1_full = self.draw_violation_highlight(f_frame, f_bbox, trajectory)
                img3_crop = self.crop_vehicle(f_frame, f_bbox)
                
                if img1_full is not None:
                    tasks.append(ImageExportTask(os.path.join(img_dir, f"{timestamp_str}_1_scene_in.jpg"), img1_full))
                if img3_crop is not None and img3_crop.size > 0:
                    tasks.append(ImageExportTask(os.path.join(img_dir, f"{timestamp_str}_3_crop_in.jpg"), img3_crop))
                    
            if l_frame is not None and l_bbox is not None:
                img2_full = self.draw_violation_highlight(l_frame, l_bbox, trajectory)
                img4_crop = self.crop_vehicle(l_frame, l_bbox)
                
                if img2_full is not None:
                    tasks.append(ImageExportTask(os.path.join(img_dir, f"{timestamp_str}_2_scene_out.jpg"), img2_full))
                if img4_crop is not None and img4_crop.size > 0:
                    tasks.append(ImageExportTask(os.path.join(img_dir, f"{timestamp_str}_4_crop_out.jpg"), img4_crop))
            
            # Đẩy tất cả task vào hàng đợi (Non-blocking I/O)
            for task in tasks:
                try:
                    self._export_queue.put_nowait(task)
                except Full:
                    logger.warning(f"⚠️ Hàng đợi ghi ảnh đầy, bỏ qua ảnh: {task.filepath}")
                    
        except Exception as e:
            logger.error(f"❌ Lỗi khi chuẩn bị ảnh bằng chứng: {e}")

    @staticmethod
    def extract_crop_for_ocr(vehicle, violation_code: str) -> Optional[np.ndarray]:
        """
        [LƯU Ý]: Hàm này được giữ lại để tương thích với kiến trúc mới.
        Việc tích hợp mô hình OCR mới (thay thế EasyOCR) sẽ sử dụng 
        dữ liệu ảnh crop trả về từ hàm này.
        """
        l_frame = vehicle.get_violation_frame(violation_code)
        l_bbox = vehicle.violation_bboxes.get(violation_code)
        
        if l_frame is not None and l_bbox is not None:
            return EvidenceGenerator.crop_vehicle(l_frame, l_bbox)
        return None

# --- END OF FILE infrastructure/evidence_generator.py ---