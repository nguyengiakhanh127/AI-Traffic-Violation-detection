import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.vehicle import Vehicle, VehicleManager
from core.lane import TrafficLane, LaneManager, ZoneManager, TrafficZone
from core.rules import TrafficLaneRule
from core.engine import ViolationRuleEngine
from core.records import ViolationRecordManager
from utils.enums import TrafficLineType, TrafficVehicleType, TrafficZoneType
from infrastructure.ai_adapters.yaml_mapper import YAML_ClassMapper
from geometry.primitives import Vertex, Vector2D
from geometry.shapes import Edge
import cv2 as cv
from ultralytics import YOLO
import numpy as np
import supervision as sv
from infrastructure.evidence_writer import VideoRingBuffer
from infrastructure.evidence_generator import EvidenceGenerator
from datetime import datetime

video_path = r"demo_data\full\giao_thong_noi_do_hn_vid1.mp4"
video = cv.VideoCapture(video_path)
if video.isOpened():
    video_fps = video.get(cv.CAP_PROP_FPS)
else:
    print("Đọc video không thành công")
video.release()
video_buffer = VideoRingBuffer(fps=int(video_fps), seconds=30)

# Init ROI, model, tracker
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
# Define LanManager
laneManager = LaneManager(
    [
        trafficLane_1,
        trafficLane_2
    ]
)
"""
# Define stop line
stop_line_junction_A = Edge(
)
# Define a TrafficLight object
sensor_light_1 = TrafficLightSensor(
)
active_sensor = []
"""
# Init model YOLO and Bytrack
model = YOLO('yolo26n_openvino_model/')
tracker = sv.ByteTrack()

# Init FPS, BoundingBox and Label for visualize
fps_overlay = sv.FPSMonitor()
corner_annotator = sv.BoxCornerAnnotator(
    thickness=2,
    color= sv.Color.GREEN
)
violate_annotator = sv.BoxAnnotator(
    thickness=2,
    color= sv.Color.RED
)
label_annotator = sv.LabelAnnotator()

# Init YAML mapper
class_mapper = YAML_ClassMapper(r"configs\coco.yaml")

vehicle_manager = VehicleManager()
record_manager = ViolationRecordManager(camera_name="Nội đô HN")
# Model result generator
results_generator = model.predict(
    source=video_path,
    stream=True,        
    classes=[1,2,3,5],
    conf=0.45,
    verbose=False,
    device= "cpu"
)

# Draw TrafficLane ROI
pts = []
for lane in laneManager.lanes:
    # Ép kiểu int ngay từ ngoài để tối ưu hóa CPU
    contour = np.array([[int(v.x), int(v.y)] for v in lane.polygon.vertices], np.int32)
    pts.append(contour)

current_time = datetime.now()

# Main loop
for result in results_generator:
    fps_overlay.tick()

    frame = result.orig_img 
    h_img, w_img = frame.shape[:2]
    current_fps = fps_overlay.fps

    detections = sv.Detections.from_ultralytics(result)
    detections = tracker.update_with_detections(detections)

    video_buffer.push(frame)

    labels = []
    formatted_detections = []
    for track_id, class_id, bbox in zip(detections.tracker_id, detections.class_id, detections.xyxy):
        vehicle_type = class_mapper.get_vehicle_type(class_id)
        x1, y1, x2, y2 = bbox

        labels.append(f"#{track_id} {vehicle_type.name}")

        # Chỉ cần truyền nguyên bản tọa độ thô vào list
        formatted_detections.append((
            track_id, vehicle_type, 
            x1.item(), y1.item(), x2.item(), y2.item()
        ))

    current_vehicles = vehicle_manager.load_from_detections(formatted_detections, frame)
    
    for vehicle in current_vehicles:
        #matched_zones = zoneManager.get_zones_at_position(vehicle.routing_point)
        current_lane = laneManager.get_lane_at_position(vehicle.routing_point)

# 1. CHỤP ẢNH FIRST SEEN: Ngay khung hình đầu tiên xe xuất hiện
        if vehicle.coordinate.age == 1 and vehicle.first_frame is None:
            vehicle.first_frame = frame.copy()
            # [FIXED]: Lấy ngay Bbox chuẩn xác từ hệ thống thay vì giả lập
            vehicle.first_bbox = vehicle.current_bbox

        # 2. RÀO CHẮN ỔN ĐỊNH: Chống phạt oan do nhiễu rìa màn hình
        if not vehicle.is_stable:
            # print("NOT WORKED") # (Nên comment lại khi chạy thực tế để tránh spam terminal)
            continue
            
        # 3. ĐỊNH TUYẾN KHÔNG GIAN
        # matched_zones = zoneManager.get_zones_at_position(vehicle.routing_point)
        current_lane = laneManager.get_lane_at_position(vehicle.routing_point)
        
        # 4. DUYỆT LUẬT
        violations = ViolationRuleEngine.inspect_vehicle(
            vehicle=vehicle, 
            lane=current_lane, 
            zones=None, 
            current_time=current_time
        )
        
        # 5. XỬ LÝ VI PHẠM & XUẤT BẰNG CHỨNG
        if violations:
            for event in violations:
                new_record = record_manager.log_violation(vehicle, event, current_time)
                
                # NẾU ĐÂY LÀ LỖI MỚI (Lập biên bản)
                if new_record:
                    # Chụp ngay tấm ảnh tại khoảnh khắc bị bắt lỗi
                    vehicle.violation_frames[event.error_name] = frame
                    vehicle.violation_bboxes[event.error_name] = vehicle.current_bbox
                    
                    # [CẬP NHẬT 1]: Lấy đường dẫn thư mục sự kiện duy nhất
                    event_folder = record_manager.get_evidence_directory(
                        violation_code=event.error_name,
                        vehicle_type_name=vehicle.vehicle_type.name,
                        current_time=current_time
                    )
                    
                    # File timestamp để nối vào đuôi ảnh/video
                    file_timestamp = current_time.strftime("%Hh%Mm%Ss_%f")[:-3]
                    
                    # [CẬP NHẬT 2]: Xuất Video vào thẳng event_folder
                    video_filepath = os.path.join(event_folder, f"{file_timestamp}_video.mp4")
                    video_buffer.trigger_export(video_filepath)
                    
                    # [CẬP NHẬT 3]: Gọi hàm sinh 4 ảnh bằng chứng vào thẳng event_folder
                    EvidenceGenerator.export_evidence_images(
                        vehicle=vehicle, 
                        violation_code=event.error_name,
                        img_dir=event_folder, 
                        timestamp_str=file_timestamp
                    )

                    # [CẬP NHẬT 4]: Xuất file JSON biên bản vào chung thư mục
                    record_manager.export_single_record_json(new_record, event_folder)


    corner_annotator.annotate(
        scene= frame,
        detections= detections
    )
                


    label_annotator.annotate(
        scene=frame,
        detections=detections,
        labels= labels
    )

    cv.putText(
        img= frame,
        text= f"FPS: {current_fps:.1f}",
        org= (20, 50),
        fontFace=cv.FONT_HERSHEY_SIMPLEX, 
        fontScale=1.2,                
        color=(0, 0, 0),           
        thickness=5 
    )

    cv.putText(
        img= frame,
        text= f"FPS: {current_fps:.1f}",
        org= (20, 50),
        fontFace=cv.FONT_HERSHEY_SIMPLEX, 
        fontScale=1.2,                
        color=(0, 255, 0),           
        thickness=2
    )

    for lane, pt in zip(laneManager.lanes, pts):
        # Vẽ đa giác làn đường
        cv.polylines(frame, [pt], isClosed=True, color=(0, 255, 255), thickness=1)
        
        # Vẽ điểm xuất phát (Đã được ép kiểu int an toàn)
        entry_pos = (int(lane.entry_point.x), int(lane.entry_point.y))
        cv.circle(frame, entry_pos, 4, (0, 0, 255), -1)
    window_name = "Detections"
    resized_image = cv.resize(frame, (1920, 1080), interpolation=cv.INTER_AREA)
    cv.namedWindow(window_name, cv.WINDOW_NORMAL)
    cv.setWindowProperty(window_name, cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)
    cv.imshow(window_name, resized_image)
    
    cv.waitKey(0)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break
cv.destroyAllWindows()
