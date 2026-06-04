import cv2
import numpy as np
import logging
from typing import Optional

try:
    from ultralytics import YOLO
    import easyocr
    HAS_ALPR_LIBS = True
except ImportError:
    HAS_ALPR_LIBS = False

logger = logging.getLogger("ALPRService")

class LicensePlateRecognizer:
    def __init__(self, yolo_model_path: str):
        self.yolo_model = None
        self.ocr_reader = None
        
        if HAS_ALPR_LIBS:
            try:
                self.yolo_model = YOLO(yolo_model_path)
                self.ocr_reader = easyocr.Reader(['en'], gpu=False) 

                logger.info("✅ Đã tải thành công mô hình ALPR (YOLO + EasyOCR)")
            except Exception as e:
                logger.error(f"❌ Lỗi tải mô hình ALPR: {e}")
        else:
            logger.warning("⚠️ Chưa cài đặt 'easyocr' hoặc 'ultralytics'. Tính năng đọc biển số bị vô hiệu hóa.")

    def recognize(self, vehicle_image: np.ndarray) -> Tuple[str, Optional[np.ndarray]]:
        """
        Trả về (Biển số xe, Ảnh cắt biển số). 
        Nếu không đọc được, trả về ("Không xác định", None)
        """
        if not HAS_ALPR_LIBS or self.yolo_model is None or self.ocr_reader is None:
            return "Không xác định", None
            
        if vehicle_image is None or vehicle_image.size == 0:
            return "Không xác định", None

        try:
            # 1. TÌM VÙNG BIỂN SỐ (YOLO)
            results = self.yolo_model(vehicle_image, verbose=False, conf=0.5)[0]
            boxes = results.boxes.xyxy.cpu().numpy()
            
            if len(boxes) == 0:
                return "Không xác định", None

            best_box = boxes[0]
            x1, y1, x2, y2 = map(int, best_box[:4])
            
            # Cắt lấy cái biển số + Padding 5px
            pad = 5
            h_img, w_img = vehicle_image.shape[:2]
            px1, py1 = max(0, x1 - pad), max(0, y1 - pad)
            px2, py2 = min(w_img, x2 + pad), min(h_img, y2 + pad)
            
            plate_img = vehicle_image[py1:py2, px1:px2]
            
            if plate_img.size == 0:
                return "Không xác định", None

            # 2. TIỀN XỬ LÝ
            gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray = clahe.apply(gray)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            gray = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)

            # 3. ĐỌC CHỮ (EasyOCR)
            allow_chars = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            ocr_result = self.ocr_reader.readtext(
                gray,
                allowlist=allow_chars,
                paragraph=False,
                text_threshold=0.4,
                low_text=0.2,
                link_threshold=0.2,
                width_ths=0.3,
                decoder='beamsearch'
            )
            
            if not ocr_result:
                # Trả về chuỗi lỗi, nhưng VẪN TRẢ VỀ ẢNH BIỂN SỐ để user tự nhìn bằng mắt thường
                return "Không xác định", plate_img 
                
            plate_text = ""
            for (bbox, text, prob) in ocr_result:
                if prob > 0.2: 
                    plate_text += text
                
            final_text = plate_text if plate_text else "Không xác định"
            
            # [CẬP NHẬT] Trả về cả Text và Ảnh Plate gốc (Chưa qua filter xám)
            return final_text, plate_img 

        except Exception as e:
            logger.error(f"❌ Lỗi trong quá trình đọc biển số: {e}")
            return "Không xác định", None