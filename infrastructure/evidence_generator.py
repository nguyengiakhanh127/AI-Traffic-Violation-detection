import cv2
import numpy as np
import os
import logging
from typing import List, Tuple
from geometry.primitives import Vertex

logger = logging.getLogger("EvidenceGen")

class EvidenceGenerator:
    
    @staticmethod
    def draw_violation_highlight(
        base_image: np.ndarray, 
        target_bbox: Tuple[int, int, int, int], 
        trajectory: List[Vertex]
    ) -> np.ndarray:
        """Vẽ highlight chiếc xe vi phạm lên ảnh toàn cảnh"""
        if base_image is None or target_bbox is None:
            return None
            
        img = base_image.copy() # [QUAN TRỌNG]: Copy để không vẽ đè lên ảnh gốc trên RAM
        x1, y1, x2, y2 = target_bbox
        
        h, w = img.shape[:2]
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w, int(x2)), min(h, int(y2))
        
        # 1. Vẽ Bbox (Màu XANH LÁ)
        color_bbox = (0, 255, 0)
        cv2.rectangle(img, (x1, y1), (x2, y2), color_bbox, 2)
        
        # 2. Vẽ vòng tròn định vị tại (x2, y1) (Màu ĐỎ)
        color_target = (0, 0, 255)
        cv2.circle(img, (x2, y1), 8, color_target, -1)
        
        # 3. Vẽ vệt lịch sử di chuyển (Trail)
        if trajectory and len(trajectory) >= 2:
            pts = np.array([[int(v.x), int(v.y)] for v in trajectory], np.int32)
            pts = pts.reshape((-1, 1, 2))
            
            cv2.polylines(img, [pts], isClosed=False, color=color_target, thickness=2)
            
            for pt in trajectory:
                cv2.circle(img, (int(pt.x), int(pt.y)), 4, color_target, -1)
                
        return img

    @staticmethod
    def crop_vehicle(base_image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """Cắt ảnh cận cảnh xe vi phạm (Ảnh 3 và Ảnh 4)."""
        if base_image is None or bbox is None:
            return None
            
        x1, y1, x2, y2 = bbox
        h, w = base_image.shape[:2]
        
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w, int(x2)), min(h, int(y2))
        
        return base_image[y1:y2, x1:x2]

    @staticmethod
    def export_evidence_images(
        vehicle, 
        violation_code: str, 
        img_dir: str, 
        timestamp_str: str
    ) -> None:
        try:
            # [CẬP NHẬT 1]: Lấy ảnh bằng hàm giải nén từ RAM
            f_frame = vehicle.get_first_frame()
            f_bbox = vehicle.first_bbox
            
            l_frame = vehicle.get_violation_frame(violation_code)
            l_bbox = vehicle.violation_bboxes.get(violation_code)
            
            # [CẬP NHẬT 2]: Lấy trajectory từ Deque và chuyển thành List
            trajectory = list(vehicle.coordinate.trajectory) if vehicle.coordinate else []
            
            # ẢNH 1 & ẢNH 3 (Scene In & Crop In)
            if f_frame is not None and f_bbox is not None:
                img1_full = EvidenceGenerator.draw_violation_highlight(f_frame, f_bbox, trajectory)
                img3_crop = EvidenceGenerator.crop_vehicle(f_frame, f_bbox)
                
                if img1_full is not None:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_1_scene_in.jpg"), img1_full)
                if img3_crop is not None and img3_crop.size > 0:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_3_crop_in.jpg"), img3_crop)
                    
            # ẢNH 2 & ẢNH 4 (Scene Out & Crop Out)
            if l_frame is not None and l_bbox is not None:
                img2_full = EvidenceGenerator.draw_violation_highlight(l_frame, l_bbox, trajectory)
                img4_crop = EvidenceGenerator.crop_vehicle(l_frame, l_bbox)
                
                if img2_full is not None:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_2_scene_out.jpg"), img2_full)
                if img4_crop is not None and img4_crop.size > 0:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_4_crop_out.jpg"), img4_crop)
                    
            logger.info(f"✅ Đã xuất thành công bộ 4 ảnh bằng chứng tại: {img_dir}")
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi sinh ảnh bằng chứng: {e}")
        
    @staticmethod
    def extract_crop_for_ocr(vehicle, violation_code: str) -> np.ndarray:
        """Trả về ma trận ảnh cắt cận cảnh chiếc xe lúc vi phạm để đưa cho mô hình AI"""
        l_frame = vehicle.get_violation_frame(violation_code)
        l_bbox = vehicle.violation_bboxes.get(violation_code)
        
        if l_frame is not None and l_bbox is not None:
            return EvidenceGenerator.crop_vehicle(l_frame, l_bbox)
        return None