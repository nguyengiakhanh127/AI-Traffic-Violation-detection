# --- START OF FILE infrastructure/visual_annotator.py ---
import cv2
import numpy as np
import supervision as sv
from typing import List

from core.vehicle import Vehicle

class VisualAnnotator:
    # Khởi tạo sẵn các bộ vẽ tĩnh của Supervision
    # TraceAnnotator vẽ vệt bánh xe mờ dần (Fading Trail) cực đẹp
    trace_annotator = sv.TraceAnnotator(
        color=sv.Color.RED, 
        position=sv.Position.BOTTOM_CENTER, 
        trace_length=30 # Độ dài vệt: 30 frame
    )


    @staticmethod
    def annotate(frame: np.ndarray, vehicles: List[Vehicle], tracked_detections, registry: dict) -> np.ndarray:
        """
        Vẽ toàn bộ đồ họa AI lên video bằng Supervision Annotators.
        """
        if frame is None:
            return frame
            
        out_img = frame.copy()
        
        # 1. Vẽ các vùng Làn đường và Vùng cấm mờ (Lớp dưới cùng)
        out_img = VisualAnnotator.draw_lane_zone_overlays(out_img, registry)
        
        # Nếu không có xe nào được AI nhận diện trong frame này, thoát sớm
        if tracked_detections is None or len(tracked_detections) == 0:
            return out_img

        # 2. Vẽ vệt bánh xe mờ dần (Trace)
        out_img = VisualAnnotator.trace_annotator.annotate(scene=out_img, detections=tracked_detections)

        # 3. [THUẬT TOÁN ĐỔI MÀU]: Duyệt qua từng xe để gán màu Bbox theo lỗi vi phạm
        for i in range(len(tracked_detections)):
            # Tách riêng lẻ từng xe trong mảng detections
            single_detection = tracked_detections[i]
            tracker_id = int(tracked_detections.tracker_id[i])
            
            # Tìm đối tượng xe tương ứng trong Core để check lỗi
            vehicle = next((v for v in vehicles if v.id == tracker_id), None)
            
            if vehicle:
                if vehicle.active_violations:
                    color = sv.Color.RED      # Đỏ (Đang vi phạm)
                elif getattr(vehicle, 'pending_violations', None):
                    color = sv.Color.ORANGE   # Cam (Chờ xét phạt)
                else:
                    color = sv.Color.GREEN    # Xanh lá (An toàn)
            else:
                color = sv.Color.GREEN
                
            # Khởi tạo bộ vẽ Hộp và Nhãn bo góc (Rounded corner) chuyên nghiệp của Supervision
            box_annotator = sv.BoxAnnotator(color=color, thickness=2)
            label_annotator = sv.LabelAnnotator(
                color=color, 
                text_color=sv.Color.WHITE,
                text_padding=4,
                text_thickness=1
            )
            
            # Tiến hành vẽ đè lên ảnh
            out_img = box_annotator.annotate(scene=out_img, detections=single_detection)
            
            # Chuẩn hóa nhãn text hiển thị
            label_text = [f"#{tracker_id} {vehicle.vehicle_type.name if vehicle else 'UNK'}"]
            out_img = label_annotator.annotate(scene=out_img, detections=single_detection, labels=label_text)
            
        return out_img

    @staticmethod
    def draw_lane_zone_overlays(frame: np.ndarray, registry: dict) -> np.ndarray:
        """Vẽ phủ màu mờ lên Làn đường và Vùng cấm"""
        out_img = frame.copy()
        
        # Vẽ Làn đường (POLYGONS)
        polygons_dict = registry.get("POLYGONS", {})
        for poly_entity in polygons_dict.values():
            pts = np.array([[int(node.sceneBoundingRect().center().x()), 
                             int(node.sceneBoundingRect().center().y())] 
                            for node in poly_entity.nodes], np.int32)
            if len(pts) >= 3:
                # Tạo đối tượng Detections giả lập chứa đa giác để ném vào bộ vẽ của Supervision
                fake_det = sv.Detections(xyxy=np.array([[0,0,0,0]]), mask=None, class_id=np.array([0]))
                # Ép tọa độ đa giác vẽ tay vào làm mặt nạ
                #out_img = VisualAnnotator.polygon_annotator.annotate(scene=out_img, detections=fake_det, custom_polygon=pts)
        
        # Vẽ Đèn giao thông (BBOXES) bằng nét vẽ OpenCV đỏ mờ
        bboxes_dict = registry.get("BBOXES", {})
        for bbox_entity in bboxes_dict.values():
            rect = bbox_entity.rect()
            x, y, w, h = int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height())
            cv2.rectangle(out_img, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(out_img, "SIGNAL_LIGHT", (x, max(20, y-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        return out_img

# --- END OF FILE infrastructure/visual_annotator.py ---