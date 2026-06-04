import sys
import os
from datetime import datetime

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import cv2 as cv
import numpy as np
from ultralytics import YOLO
import supervision as sv

from core.vehicle import Vehicle, VehicleManager
from core.lane import TrafficLane, LaneManager, ZoneManager, TrafficZone
from core.rules import TrafficLaneRule
# [CẬP NHẬT 1]: Import Engine, Context và các Luật cụ thể
from core.engine import (
    ViolationRuleEngine, WrongWayRule, LineCrossingRule, 
    WrongLaneRule, InspectionContext
)
from core.records import ViolationRecordManager
from utils.enums import TrafficLineType, TrafficVehicleType, TrafficZoneType
from infrastructure.ai_adapters.yaml_mapper import YAML_ClassMapper
from geometry.primitives import Vertex, Vector2D
from geometry.shapes import Edge
from infrastructure.evidence_writer import VideoRingBuffer
from infrastructure.evidence_generator import EvidenceGenerator

# ==========================================
# 1. SETUP VIDEO & CAMERA
# ==========================================
video_path = r"demo_data\full\giao_thong_noi_do_hn_vid1.mp4"
video = cv.VideoCapture(video_path)
if video.isOpened():
    video_fps = video.get(cv.CAP_PROP_FPS)
else:
    print("Đọc video không thành công")
    sys.exit()
video.release()

video_buffer = VideoRingBuffer(fps=int(video_fps), seconds=10) # Tối ưu RAM: giữ 15s thôi

# ==========================================
# 2. SETUP ROI (LÀN ĐƯỜNG)
# ==========================================
lane_1 = [
    Edge(Vertex(612, 1199), Vertex(1418, 1198), TrafficLineType.ENTRY),
    Edge(Vertex(1418, 1198), Vertex(1256, 804), TrafficLineType.DASHED),
    Edge(Vertex(1256, 804), Vertex(734, 813), TrafficLineType.EXIT),
    Edge(Vertex(734, 813), Vertex(612, 1199), TrafficLineType.SOLID)
]
trafficLane_1 = TrafficLane("1", lane_1, TrafficLaneRule({TrafficVehicleType.CAR, TrafficVehicleType.TRUCK, TrafficVehicleType.MOTORCYCLE}))

lane_2 = [
    Edge(Vertex(701, 864), Vertex(0, 886), TrafficLineType.ENTRY),
    Edge(Vertex(0, 886), Vertex(0, 1199), TrafficLineType.DASHED),
    Edge(Vertex(0, 1199), Vertex(592, 1199), TrafficLineType.EXIT),
    Edge(Vertex(592, 1199), Vertex(701, 864), TrafficLineType.SOLID)
]
trafficLane_2 = TrafficLane("2", lane_2, TrafficLaneRule({TrafficVehicleType.CAR, TrafficVehicleType.TRUCK, TrafficVehicleType.MOTORCYCLE}))

laneManager = LaneManager([trafficLane_1, trafficLane_2])

# ==========================================
# 3. SETUP AI & MANAGERS
# ==========================================
model = YOLO(r'model\yolo\openVINO_format\vehicle_detection\best_openvino_model')
tracker = sv.ByteTrack()

fps_overlay = sv.FPSMonitor()
corner_annotator = sv.BoxCornerAnnotator(thickness=2, color=sv.Color.GREEN)
violate_annotator = sv.BoxAnnotator(thickness=2, color=sv.Color.RED)
label_annotator = sv.LabelAnnotator()

class_mapper = YAML_ClassMapper(r"configs\hutech.yaml")

vehicle_manager = VehicleManager()
vehicle_manager._smoother.alpha = 0.8 # Tăng độ nhạy (gần Raw hơn)
vehicle_manager._smoother.max_growth_ratio = 1.15

record_manager = ViolationRecordManager(camera_name="Nội đô HN")

# [CẬP NHẬT 2]: Khởi tạo Động cơ duyệt luật (Strategy Pattern)
rule_engine = ViolationRuleEngine()
rule_engine.add_rule(WrongWayRule())
rule_engine.add_rule(LineCrossingRule())
rule_engine.add_rule(WrongLaneRule())

# Vẽ đa giác làn đường tĩnh một lần
pts = [np.array([[int(v.x), int(v.y)] for v in lane.polygon.vertices], np.int32) for lane in laneManager.lanes]


# ==========================================
# 4. MAIN LOOP (VÒNG LẶP XỬ LÝ)
# ==========================================
results_generator = model.predict(
    source=video_path, stream=True, conf=0.3, verbose=False
)

for result in results_generator:
    fps_overlay.tick()
    frame = result.orig_img 
    h_img, w_img = frame.shape[:2]
    current_fps = fps_overlay.fps
    current_time = datetime.now()

    # 1. AI Tracking
    detections = sv.Detections.from_ultralytics(result)
    detections = tracker.update_with_detections(detections)
    video_buffer.push(frame)

    # 2. Format Dữ liệu
    labels = []
    formatted_detections = []
    for track_id, class_id, bbox in zip(detections.tracker_id, detections.class_id, detections.xyxy):
        vehicle_type = class_mapper.get_vehicle_type(class_id)
        x1, y1, x2, y2 = bbox
        labels.append(f"#{track_id} {vehicle_type.name}")
        formatted_detections.append((track_id, vehicle_type, x1.item(), y1.item(), x2.item(), y2.item()))

    # 3. Quản lý Phương tiện (VehicleManager tự nén ảnh first_frame vào RAM)
    current_vehicles = vehicle_manager.load_from_detections(
        formatted_detections, frame_shape=(h_img, w_img), raw_frame=frame
    )
    
    # 4. Xử lý Logic Nghiệp vụ (Core)
    for vehicle in current_vehicles:
        
        if not vehicle.is_stable:
            continue
            
        current_lane = laneManager.get_lane_at_position(vehicle.routing_point)
        
        # [CẬP NHẬT 3]: Đóng gói Bối cảnh và chạy Engine
        context = InspectionContext(lane=current_lane, zones=[], current_time=current_time)
        violations = rule_engine.inspect_vehicle(vehicle, context)
        
        # 5. Lưu Bằng Chứng
        if violations:
            for event in violations:
                # [CẬP NHẬT 4]: Trả về record và đường dẫn thư mục
                log_result = record_manager.log_violation(vehicle, event, current_time)
                
                if log_result:
                    new_record, event_folder = log_result
                    
                    # Nén ảnh khoảnh khắc vi phạm vào RAM
                    vehicle.add_violation_frame(event.error_name, frame, vehicle.current_bbox)
                    
                    file_timestamp = current_time.strftime("%Hh%Mm%Ss_%f")[:-3]
                    
                    # Kích hoạt xuất Video
                    video_filepath = os.path.join(event_folder, f"{file_timestamp}_video.mp4")
                    video_buffer.trigger_export(video_filepath)
                    
                    # Kích hoạt sinh Ảnh 
                    EvidenceGenerator.export_evidence_images(
                        vehicle=vehicle, 
                        violation_code=event.error_name,
                        img_dir=event_folder, 
                        timestamp_str=file_timestamp
                    )
                # NOTE: Json đã được tự động lưu trong hàm log_violation nhờ JsonRecordStorage
    # ==========================================
    # 5. VẼ LÊN MÀN HÌNH (VISUALIZATION)
    # ==========================================
    corner_annotator.annotate(scene=frame, detections=detections)
    label_annotator.annotate(scene=frame, detections=detections, labels=labels)

    cv.putText(frame, f"FPS: {current_fps:.1f}", (20, 50), cv.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 5)
    cv.putText(frame, f"FPS: {current_fps:.1f}", (20, 50), cv.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 2)
    
    
    window_name = "Detections"
    cv.imshow(window_name, frame)
    
    # [CẬP NHẬT 5]: Sửa lỗi đứng hình (waitKey(0))
    if cv.waitKey(1) & 0xFF == ord('q'):
        break

video_buffer.wait_for_export_finish(timeout_sec=20) 

cv.destroyAllWindows()