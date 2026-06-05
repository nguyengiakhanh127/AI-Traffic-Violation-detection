# --- START OF FILE infrastructure/visual_annotator.py ---

import cv2
import numpy as np
import supervision as sv
from typing import List, Dict, Optional
from dataclasses import dataclass

from core.vehicle import Vehicle
from utils.enums import TrafficVehicleType

@dataclass
class AnnotatorConfig:
    is_enabled: bool = True
    show_violators_only: bool = False
    show_trails: bool = True
    show_rois: bool = True
    visible_classes: Dict[TrafficVehicleType, bool] = None
    
    # [CẬP NHẬT]: Loại bỏ PENDING, chỉ giữ An toàn (Xanh) và Vi phạm (Đỏ)
    violation_colors = {
        "SAFE": (0, 255, 0),        
        "VIOLATING": (255, 0, 0)    
    }

    def __post_init__(self):
        if self.visible_classes is None:
            self.visible_classes = {v_type: True for v_type in TrafficVehicleType}

class VisualAnnotator:
    def __init__(self, config: Optional[AnnotatorConfig] = None):
        self.config = config or AnnotatorConfig()
        
        self._init_state_annotators()
        
        self.trace_annotator = sv.TraceAnnotator(
            color=sv.Color.WHITE, 
            position=sv.Position.BOTTOM_CENTER, 
            trace_length=45,
            thickness=2
        )

    def _init_state_annotators(self):
        """Khởi tạo 2 bộ vẽ tĩnh cho An Toàn và Vi Phạm"""
        color_safe = sv.Color.from_rgb_tuple(self.config.violation_colors["SAFE"])
        color_viol = sv.Color.from_rgb_tuple(self.config.violation_colors["VIOLATING"])

        # Box dùng màu theo trạng thái
        self.box_ann_safe = sv.BoxAnnotator(color=color_safe, thickness=2)
        self.box_ann_violating = sv.BoxAnnotator(color=color_viol, thickness=2)

        # [CẬP NHẬT]: Label luôn dùng Nền Đen, Chữ Trắng để dễ đọc nhất
        black_color = sv.Color.from_rgb_tuple((0, 0, 0))
        self.lbl_ann = sv.LabelAnnotator(
            color=black_color, 
            text_color=sv.Color.WHITE, 
            text_padding=5,
            text_thickness=1
        )

    def update_config(self, new_config: AnnotatorConfig) -> None:
        self.config = new_config
        self._init_state_annotators()

    def annotate(self, frame: np.ndarray, vehicles: List[Vehicle], tracked_detections: sv.Detections, registry: dict) -> np.ndarray:
        if frame is None:
            return None
            
        out_img = frame.copy()
        out_img = self._draw_spatial_overlays(out_img, registry)
        
        if not self.config.is_enabled or tracked_detections is None or len(tracked_detections) == 0:
            return out_img

        num_dets = len(tracked_detections)
        
        # 1. Tạo 2 Mask nhị phân
        mask_safe = np.zeros(num_dets, dtype=bool)
        mask_violating = np.zeros(num_dets, dtype=bool)
        labels = []

        vehicle_map = {v.id: v for v in vehicles}

        # 2. Phân loại xe
        for i, (track_id, class_id) in enumerate(zip(tracked_detections.tracker_id, tracked_detections.class_id)):
            v_id = int(track_id)
            vehicle = vehicle_map.get(v_id)
            
            labels.append("") 

            if not vehicle:
                if not self.config.show_violators_only:
                    mask_safe[i] = True
                    labels[i] = f"#{v_id} UNK"
                continue

            if not self.config.visible_classes.get(vehicle.vehicle_type, True):
                continue

            is_violating = len(vehicle.active_violations) > 0

            if is_violating:
                mask_violating[i] = True
            elif not self.config.show_violators_only:
                mask_safe[i] = True
                
            if mask_violating[i] or mask_safe[i]:
                labels[i] = f"#{v_id} {vehicle.vehicle_type.name}"

        # 3. Vẽ Vết Bánh Xe (Trail)
        if self.config.show_trails:
            mask_all_visible = mask_safe | mask_violating
            dets_visible = tracked_detections[mask_all_visible]
            if len(dets_visible) > 0:
                out_img = self.trace_annotator.annotate(scene=out_img, detections=dets_visible)

        labels_np = np.array(labels)

        # 4. Vẽ Nhóm An Toàn
        dets_safe = tracked_detections[mask_safe]
        if len(dets_safe) > 0:
            out_img = self.box_ann_safe.annotate(scene=out_img, detections=dets_safe)
            out_img = self.lbl_ann.annotate(scene=out_img, detections=dets_safe, labels=labels_np[mask_safe].tolist())

        # 5. Vẽ Nhóm Vi Phạm
        dets_violating = tracked_detections[mask_violating]
        if len(dets_violating) > 0:
            out_img = self.box_ann_violating.annotate(scene=out_img, detections=dets_violating)
            out_img = self.lbl_ann.annotate(scene=out_img, detections=dets_violating, labels=labels_np[mask_violating].tolist())

        return out_img

    def _draw_spatial_overlays(self, frame: np.ndarray, registry: dict) -> np.ndarray:
        overlay = frame.copy()
        
        polygons_dict = registry.get("POLYGONS", {})
        for poly_entity in polygons_dict.values():
            pts = np.array([[int(node.sceneBoundingRect().center().x()), 
                             int(node.sceneBoundingRect().center().y())] 
                            for node in poly_entity.nodes], np.int32)
            if len(pts) >= 3:
                cv2.fillPoly(overlay, [pts], color=(255, 100, 100))
                cv2.polylines(overlay, [pts], isClosed=True, color=(255, 0, 0), thickness=2)
        
        alpha = 0.3
        cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
        
        bboxes_dict = registry.get("BBOXES", {})
        for bbox_entity in bboxes_dict.values():
            rect = bbox_entity.rect()
            x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
            
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 1)
            cv2.putText(frame, "TRAFFIC LIGHT", (x, max(15, y-5)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1, cv2.LINE_AA)

        return frame

# --- END OF FILE infrastructure/visual_annotator.py ---