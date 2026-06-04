import cv2
import numpy as np
from typing import Tuple, Optional, Dict, List
from geometry.shapes import Edge
from utils.enums import TrafficLightColor

class TrafficLight:
    DEFAULT_HSV_RANGES = {
        TrafficLightColor.RED: [
            (np.array([0, 120, 120]), np.array([10, 255, 255])),
            (np.array([170, 120, 120]), np.array([180, 255, 255]))
        ],
        TrafficLightColor.YELLOW: [
            (np.array([15, 120, 120]), np.array([35, 255, 255]))
        ],
        TrafficLightColor.GREEN: [
            (np.array([40, 120, 120]), np.array([90, 255, 255]))
        ]
    }

    def __init__(
        self, 
        light_id: str, 
        bbox_rect: Tuple[int, int, int, int], 
        stop_line: Edge, 
        right_turn_line: Optional[Edge] = None, 
        active_pixel_ratio: float = 0.15 
    ):
        self.light_id = light_id
        x, y, w, h = bbox_rect
        self.bbox = (int(x), int(y), int(x + w), int(y + h))
        
        self.stop_line = stop_line
        self.right_turn_line = right_turn_line
        self.active_pixel_ratio = active_pixel_ratio
        
        self.hsv_ranges = self.DEFAULT_HSV_RANGES
        self.current_color = TrafficLightColor.OFF

    def update_state(self, frame: np.ndarray) -> TrafficLightColor:
        """Trích xuất vùng ảnh đèn và quét màu"""
        xmin, ymin, xmax, ymax = self.bbox
        h_img, w_img = frame.shape[:2]

        xmin, ymin = max(0, xmin), max(0, ymin)
        xmax, ymax = min(w_img, xmax), min(h_img, ymax)

        if (xmax - xmin) <= 0 or (ymax - ymin) <= 0:
            self.current_color = TrafficLightColor.OFF
            return self.current_color

        roi = frame[ymin:ymax, xmin:xmax]
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        
        color_ratios = {}

        for color, ranges in self.hsv_ranges.items():
            combined_mask = np.zeros(hsv_roi.shape[:2], dtype=np.uint8)
            for lower, upper in ranges:
                mask = cv2.inRange(hsv_roi, lower, upper)
                combined_mask = cv2.bitwise_or(combined_mask, mask)
            
            total_pixels = combined_mask.size
            active_pixels = cv2.countNonZero(combined_mask)
            ratio = active_pixels / total_pixels if total_pixels > 0 else 0.0
            color_ratios[color] = ratio

        dominant_color = max(color_ratios, key=color_ratios.get)
        dominant_ratio = color_ratios[dominant_color]

        if dominant_ratio >= self.active_pixel_ratio:
            self.current_color = dominant_color
        else:
            self.current_color = TrafficLightColor.OFF

        return self.current_color