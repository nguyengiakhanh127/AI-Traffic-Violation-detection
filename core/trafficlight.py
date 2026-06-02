# --- START OF FILE traffic_light.py ---
import cv2
import numpy as np
from typing import Tuple, Optional, Dict, List
from geometry.shapes import Edge
#from utils.enums import TrafficLightColor

class TrafficLight:
    # [CẬP NHẬT: Định nghĩa bộ dải màu HSV mặc định]
    # Đỏ có 2 dải do đặc thù trục Hue. Vàng và Xanh có 1 dải.
    DEFAULT_HSV_RANGES = {
        TrafficLightColor.RED: [
            (np.array([0, 70, 70]), np.array([10, 255, 255])),
            (np.array([170, 70, 70]), np.array([180, 255, 255]))
        ],
        TrafficLightColor.YELLOW: [
            (np.array([15, 70, 70]), np.array([35, 255, 255]))
        ],
        TrafficLightColor.GREEN: [
            (np.array([36, 70, 70]), np.array([89, 255, 255]))
        ]
    }

    def __init__(
        self, 
        light_id: str, 
        bbox_xyxy: Tuple[int, int, int, int], 
        stop_line: Edge, 
        # [CẬP NHẬT: Liên kết vạch rẽ phải tùy chọn]
        right_turn_line: Optional[Edge] = None, 
        active_pixel_ratio: float = 0.25,
        # [CẬP NHẬT: Hỗ trợ người dùng truyền dải màu HSV tùy biến cho từng cột đèn]
        custom_hsv_ranges: Optional[Dict[TrafficLightColor, List[Tuple[np.ndarray, np.ndarray]]]] = None
    ):
        self.light_id = light_id
        self.bbox = bbox_xyxy
        self.stop_line = stop_line
        self.right_turn_line = right_turn_line
        self.active_pixel_ratio = active_pixel_ratio
        
        # Áp dụng dải màu tùy biến nếu có, ngược lại dùng mặc định
        self.hsv_ranges = custom_hsv_ranges if custom_hsv_ranges is not None else self.DEFAULT_HSV_RANGES
        
        # Lớp thuần logic lưu trữ trạng thái hiện tại (Mặc định là OFF)
        self.current_color = TrafficLightColor.OFF

    def update_state(self, frame: np.ndarray) -> TrafficLightColor:
        """
        [CẬP NHẬT: Logic phân tích đa màu thông minh]
        Quét mask cho cả 3 màu, tính toán tỷ lệ phát sáng, màu nào có tỷ lệ 
        lớn nhất và vượt ngưỡng kích hoạt sẽ là màu hiện tại của đèn.
        """
        xmin, ymin, xmax, ymax = self.bbox
        h, w, _ = frame.shape

        xmin = max(0, int(xmin))
        ymin = max(0, int(ymin))
        xmax = min(w, int(xmax))
        ymax = min(h, int(ymax))

        if (xmax - xmin) <= 0 or (ymax - ymin) <= 0:
            self.current_color = TrafficLightColor.OFF
            return self.current_color

        # Trích xuất ROI và chuyển sang hệ màu HSV
        roi = frame[ymin:ymax, xmin:xmax]
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        color_ratios = {}

        # Quét qua từng cấu hình màu (Đỏ, Vàng, Xanh)
        for color, ranges in self.hsv_ranges.items():
            combined_mask = np.zeros(hsv_roi.shape[:2], dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.inRange(hsv_roi, lower, upper)
                combined_mask = cv2.bitwise_or(combined_mask, mask)
            
            total_pixels = combined_mask.size
            active_pixels = cv2.countNonZero(combined_mask)
            ratio = active_pixels / total_pixels if total_pixels > 0 else 0.0
            color_ratios[color] = ratio

        # Tìm màu có tỷ lệ phát sáng lớn nhất
        dominant_color = max(color_ratios, key=color_ratios.get)
        dominant_ratio = color_ratios[dominant_color]

        # Nếu màu chiếm ưu thế lớn hơn tỷ lệ kích hoạt tối thiểu -> Ghi nhận màu đó
        if dominant_ratio >= self.active_pixel_ratio:
            self.current_color = dominant_color
        else:
            self.current_color = TrafficLightColor.OFF

        return self.current_color

