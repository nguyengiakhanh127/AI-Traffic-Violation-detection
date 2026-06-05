# --- START OF FILE infrastructure/ai_adapters/alpr/plate_recognizer.py ---

import cv2
import numpy as np
import logging
from typing import Tuple, Optional
from fast_plate_ocr import ONNXPlateRecognizer
import re

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

logger = logging.getLogger("ALPRService")

class LicensePlateRecognizer:
    """
    Hệ thống nhận diện biển số 2 Giai đoạn (2-Stage ALPR Pipeline):
    - Giai đoạn 1: YOLO phát hiện và cắt khung chứa biển số từ ảnh cận cảnh xe.
    - Giai đoạn 2: Fast-Plate-OCR đọc ký tự từ ảnh biển số đã cắt.
    """
    def __init__(self, yolo_model_path: str):
        self.yolo_model_path = yolo_model_path
        self.plate_detector = None
        self.ocr_reader = None
        
        self._initialize_models()

    def _initialize_models(self) -> None:
        """Nạp các mô hình vào bộ nhớ RAM/GPU (Chỉ gọi 1 lần khi khởi động)"""
        try:
            if HAS_YOLO:
                logger.info(f"Đang nạp mô hình phát hiện biển số (YOLO) từ: {self.yolo_model_path}")
                # task='detect' giúp tối ưu quá trình load ONNX/OpenVINO
                self.plate_detector = YOLO(self.yolo_model_path, task='detect')
            else:
                logger.error("❌ Không tìm thấy thư viện Ultralytics (YOLO). ALPR bị vô hiệu hóa.")

            logger.info("Đang nạp mô hình đọc ký tự (fast-plate-ocr)...")
            # Tự động chọn thiết bị ('cuda' hoặc 'cpu') tùy cấu hình phần cứng
            self.ocr_reader = ONNXPlateRecognizer("global-plates-mobile-vit-v2-model")
            logger.info("✅ Hệ thống ALPR (Fast-Plate-OCR) đã sẵn sàng.")
            
        except Exception as e:
            logger.error(f"❌ Lỗi khởi tạo hệ thống ALPR: {e}")

    def recognize(self, vehicle_crop: np.ndarray) -> Tuple[str, Optional[np.ndarray]]:
        if vehicle_crop is None or self.plate_detector is None or self.ocr_reader is None:
            return "Không xác định", vehicle_crop

        try:
            # ==========================================
            # STAGE 1: PHÁT HIỆN BIỂN SỐ BẰNG YOLO
            # ==========================================
            results = self.plate_detector(vehicle_crop, verbose=False, conf=0.3)[0]
            boxes = results.boxes
            
            if len(boxes) == 0:
                return "Không xác định", vehicle_crop

            best_box = max(boxes, key=lambda b: float(b.conf[0]))
            
            x1, y1, x2, y2 = map(int, best_box.xyxy[0].tolist())
            conf = float(best_box.conf[0])
            
            h, w = vehicle_crop.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            
            plate_crop = vehicle_crop[y1:y2, x1:x2]
            
            if plate_crop.size == 0:
                return "Không xác định", vehicle_crop

            # ==========================================
            # STAGE 2: ĐỌC VÀ LÀM SẠCH KÝ TỰ (POST-PROCESSING)
            # ==========================================
            gray_plate_crop = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
            
            ocr_result = self.ocr_reader.run(gray_plate_crop)
            
            if isinstance(ocr_result, list) and len(ocr_result) > 0:
                raw_text = "".join(ocr_result)
            elif isinstance(ocr_result, str):
                raw_text = ocr_result
            else:
                raw_text = str(ocr_result) if ocr_result else ""
            
            # [CẬP NHẬT TRỌNG TÂM]: Làm sạch chuỗi bằng Regex
            # Lọc bỏ mọi ký tự không phải là Chữ cái (a-z, A-Z) và Số (0-9)
            clean_text = re.sub(r'[^A-Za-z0-9]', '', raw_text).upper()
            
            # Đảm bảo biển số thu được không bị rỗng sau khi làm sạch
            if len(clean_text) < 3: # Biển số thực tế thường dài hơn 3 ký tự
                plate_text = "Không xác định"
            else:
                # [Tùy chọn]: Nếu bạn muốn thêm lại dấu gạch nối giữa cụm chữ và số cho dễ nhìn
                # Ví dụ: 29A12345 -> 29A-12345, bạn có thể viết thêm logic regex ở đây.
                # Hiện tại, hệ thống sẽ lưu chuỗi sạch nguyên khối (VD: 29A12345).
                plate_text = clean_text
            
            # ==========================================
            # VẼ KẾT QUẢ TRẢ VỀ (VISUALIZATION)
            # ==========================================
            drawn_image = vehicle_crop.copy()
            
            cv2.rectangle(drawn_image, (x1, y1), (x2, y2), (0, 255, 255), 2)
            
            text_size, _ = cv2.getTextSize(plate_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            text_w, text_h = text_size
            cv2.rectangle(drawn_image, (x1, y1 - text_h - 10), (x1 + text_w + 10, y1), (0, 0, 0), -1)
            cv2.putText(drawn_image, plate_text, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            return plate_text, drawn_image

        except Exception as e:
            logger.error(f"❌ Lỗi trong quá trình suy luận ALPR: {e}")
            return "Không xác định", vehicle_crop

# --- END OF FILE infrastructure/ai_adapters/alpr/plate_recognizer.py ---