# --- START UPDATE: evidence_generator.py ---
import cv2
import numpy as np
import os
import logging
from typing import List
from geometry.primitives import Vertex

logger = logging.getLogger("EvidenceGen")

class EvidenceGenerator:
    
    @staticmethod
    def draw_violation_highlight(
        base_image: np.ndarray, 
        target_bbox: tuple, 
        trajectory: List[Vertex]
    ) -> np.ndarray:
        """
        Vẽ highlight chiếc xe vi phạm lên ảnh toàn cảnh theo chuẩn giao diện GTVT.
        - target_bbox: (x1, y1, x2, y2) của xe vi phạm.
        - trajectory: Danh sách các điểm lịch sử (từ lúc vào đến lúc ra).
        """
        if base_image is None or target_bbox is None:
            return None
            
        img = base_image
        x1, y1, x2, y2 = target_bbox
        
        # Đảm bảo tọa độ nằm trong khung hình an toàn
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        # 1. Vẽ Bbox cho xe vi phạm (Màu XANH LÁ)
        color_bbox = (0, 255, 0) # BGR: Xanh lá
        cv2.rectangle(img, (x1, y1), (x2, y2), color_bbox, 2)
        
        # 2. Vẽ vòng tròn định vị tại (x2, y1) (Màu ĐỎ, filled)
        color_target = (0, 0, 255) # BGR: Đỏ
        cv2.circle(img, (x2, y1), 8, color_target, -1) # thickness=-1 để tô kín
        
        # 3. Vẽ vệt lịch sử di chuyển (Màu ĐỎ cho cả line và circle)
        if trajectory and len(trajectory) >= 2:
            pts = np.array([[int(v.x), int(v.y)] for v in trajectory], np.int32)
            pts = pts.reshape((-1, 1, 2))
            
            # Vẽ đường nối line màu đỏ
            cv2.polylines(img, [pts], isClosed=False, color=color_target, thickness=2)
            
            # Vẽ chấm tròn màu đỏ đại diện cho các tọa độ
            for pt in trajectory:
                cv2.circle(img, (int(pt.x), int(pt.y)), 4, color_target, -1)
                
        return img

    @staticmethod
    def crop_vehicle(base_image: np.ndarray, bbox: tuple) -> np.ndarray:
        """
        Cắt ảnh cận cảnh xe vi phạm (Ảnh 3 và Ảnh 4).
        """
        if base_image is None or bbox is None:
            return None
            
        x1, y1, x2, y2 = bbox
        h, w = base_image.shape[:2]
        
        # Đảm bảo không cắt lẹm ra ngoài ma trận ảnh gây crash
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        
        crop_img = base_image[y1:y2, x1:x2]
        return crop_img

    @staticmethod
    def export_evidence_images(
        vehicle, 
        violation_code: str, # Nhận thêm mã lỗi để lấy đúng ảnh
        img_dir: str, 
        timestamp_str: str
    ) -> None:

        try:
            # ẢNH LÚC MỚI VÀO (Lấy từ First Seen)
            f_frame = getattr(vehicle, 'first_frame', None)
            f_bbox = getattr(vehicle, 'first_bbox', None)
            
            # ẢNH LÚC VI PHẠM (Lấy từ kho lưu trữ ảnh vi phạm theo mã lỗi)
            l_frame = vehicle.violation_frames.get(violation_code)
            l_bbox = vehicle.violation_bboxes.get(violation_code)
            
            trajectory = vehicle.coordinate.full_trajectory if hasattr(vehicle.coordinate, 'full_trajectory') else []
            
            # ---------------------------------------------
            # ẢNH 1 (Scene In) & ẢNH 3 (Crop In)
            # ---------------------------------------------
            if f_frame is not None and f_bbox is not None:
                # Ảnh 1: Ảnh gốc + Bbox Xanh + Chấm Đỏ + Vệt Đỏ (toàn bộ trajectory)
                img1_full = EvidenceGenerator.draw_violation_highlight(f_frame, f_bbox, trajectory)
                # Ảnh 3: Chỉ Crop xe từ ảnh gốc
                img3_crop = EvidenceGenerator.crop_vehicle(f_frame, f_bbox)
                
                if img1_full is not None:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_1_scene_in.jpg"), img1_full)
                if img3_crop is not None and img3_crop.size > 0:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_3_crop_in.jpg"), img3_crop)
                    
            # ---------------------------------------------
            # ẢNH 2 (Scene Out) & ẢNH 4 (Crop Out)
            # ---------------------------------------------
            if l_frame is not None and l_bbox is not None:
                # Ảnh 2: Ảnh gốc chốt lỗi + Bbox Xanh + Chấm Đỏ + Vệt Đỏ (toàn bộ trajectory)
                img2_full = EvidenceGenerator.draw_violation_highlight(l_frame, l_bbox, trajectory)
                # Ảnh 4: Chỉ Crop xe lúc lỗi
                img4_crop = EvidenceGenerator.crop_vehicle(l_frame, l_bbox)
                
                if img2_full is not None:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_2_scene_out.jpg"), img2_full)
                if img4_crop is not None and img4_crop.size > 0:
                    cv2.imwrite(os.path.join(img_dir, f"{timestamp_str}_4_crop_out.jpg"), img4_crop)
                    
            logger.info(f"✅ Đã xuất thành công bộ 4 ảnh bằng chứng tại: {img_dir}")
            
        except Exception as e:
            logger.error(f"❌ Lỗi khi sinh ảnh bằng chứng: {e}")

# --- END UPDATE ---