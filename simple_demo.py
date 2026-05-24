import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.vehicle import Vehicle, VehicleManager
from core.lane import TrafficLane, LaneManager, ZoneManager, TrafficZone
from core.rules import TrafficLaneRule
from core.engine import ViolationRuleEngine
from utils.enums import TrafficLineType, TrafficVehicleType, TrafficZoneType
from infrastructure.ai_adapters.yaml_mapper import YAML_ClassMapper
from geometry.primitives import Vertex, Vector2D
from geometry.shapes import Edge
import cv2 as cv
from ultralytics import YOLO
import numpy as np
import supervision as sv
from datetime import datetime

video_path = r"demo_data\clips\giao_thong_noi_do_tq_clip_RedLightStop.mp4"

# Init ROI, model, tracker
lane_1= [
    Edge(Vertex(851, 673), Vertex(1134, 673), TrafficLineType.VIRTUAL),
    Edge(Vertex(1134, 673), Vertex(836, 349), TrafficLineType.DASHED),
    Edge(Vertex(836, 349), Vertex(695, 353), TrafficLineType.VIRTUAL),
    Edge(Vertex(695, 353), Vertex(851, 673), TrafficLineType.SOLID)
]
trafficLane_1 = TrafficLane("1", lane_1, TrafficLaneRule({TrafficVehicleType.CAR, TrafficVehicleType.TRUCK, TrafficVehicleType.MOTORCYCLE}))
lane_2= [
    Edge(Vertex(68, 673), Vertex(847, 673), TrafficLineType.VIRTUAL),
    Edge(Vertex(847, 673), Vertex(694, 352), TrafficLineType.SOLID),
    Edge(Vertex(694, 352), Vertex(293, 363), TrafficLineType.VIRTUAL),
    Edge(Vertex(293, 363), Vertex(68, 673), TrafficLineType.SOLID)
]
trafficLane_2 = TrafficLane("2", lane_2, TrafficLaneRule({TrafficVehicleType.CAR, TrafficVehicleType.TRUCK, TrafficVehicleType.MOTORCYCLE}))
lane_3= [
    Edge(Vertex(0, 505), Vertex(192, 505), TrafficLineType.VIRTUAL),
    Edge(Vertex(192, 505), Vertex(289, 364), TrafficLineType.SOLID),
    Edge(Vertex(289, 364), Vertex(153, 363), TrafficLineType.VIRTUAL),
    Edge(Vertex(153, 363), Vertex(0, 505), TrafficLineType.DASHED)
]
trafficLane_3 = TrafficLane("3", lane_3, TrafficLaneRule({TrafficVehicleType.CAR, TrafficVehicleType.TRUCK, TrafficVehicleType.MOTORCYCLE}))
# Define LanManager
laneManager = LaneManager(
    [
        trafficLane_1,
        trafficLane_2,
        trafficLane_3
    ]
)
trafficZone_1 = TrafficZone(
    zone_id= 1,
    zone_type= TrafficZoneType.NO_PARKING,
    polygon= trafficLane_2.polygon
)
zoneManager = ZoneManager(
    [
        trafficZone_1
    ]
)
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

class_mapper = YAML_ClassMapper(r"configs\coco.yaml")
vehicle_manager = VehicleManager()

# Model result generator
results_generator = model.predict(
    source=video_path,
    stream=True,        
    classes=[1,2,3,5],
    conf=0.45,
    verbose=False,
    device= "cpu"
)
frame = cv.imread(r"demo_data\imgs\giao_thong_noi_do_tq_anh.jpg")
pts = []
for idx, lane in enumerate(laneManager.lanes):
    pts.append(np.array([[v.x, v.y] for v in lane.polygon.vertices], np.int32))
current_time = datetime.now()
for result in results_generator:
    fps_overlay.tick()

    frame = result.orig_img 
    current_fps = fps_overlay.fps

    detections = sv.Detections.from_ultralytics(result)
    detections = tracker.update_with_detections(detections)

    labels = []
    formatted_detections = []
    
    for track_id, class_id, bbox in zip(detections.tracker_id, detections.class_id, detections.xyxy):
        vehicle_type = class_mapper.get_vehicle_type(class_id)
        x1, y1, x2, y2 = bbox

        labels.append(f"#{track_id} {vehicle_type}")
        pos_centroid = Vertex(((x1 + x2) / 2).item(), ((y1 + y2) / 2).item())    
        pos_footprint = Vertex(((x1 + x2) / 2).item(), 
                               (y1 + 0.8*(y2 - y1)).item() if vehicle_type == TrafficVehicleType.MOTORCYCLE else  (y1 + 0.7*(y2 - y1)).item() 
                               )               
        pos_left = Vertex(x1.item(), y2.item())                                 
        pos_right = Vertex(x2.item(), y2.item())                                

        formatted_detections.append((track_id, vehicle_type, pos_centroid, pos_footprint, pos_left, pos_right))

    current_vehicles = vehicle_manager.process_frame_detections(formatted_detections)
    for vehicle in current_vehicles:
        if vehicle.track_id == 39:
            
            matched_zones = zoneManager.get_zones_at_position(vehicle.footprint)

            lanes_to_inspect = laneManager.get_lane_at_position(vehicle.current_position)
            
            if lanes_to_inspect:
                violations = ViolationRuleEngine.inspect_vehicle(
                    vehicle=vehicle, 
                    lane=lane, 
                    zones=matched_zones, 
                    current_time=current_time
                )
                if violations:
                    print(violations)
            else:
                violations = ViolationRuleEngine.inspect_vehicle(
                    vehicle=vehicle, 
                    lane=None, 
                    zones=matched_zones, 
                    current_time=current_time
                )
                if violations:
                    print(violations)

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

    for idx in range(len(laneManager.lanes)):
        cv.polylines(frame, [pts[idx]], isClosed=True, color=(0, 255, 255), thickness=1)
        cv.circle(frame, (laneManager.lanes[idx].entry_point.x, laneManager.lanes[idx].entry_point.y), 4, (0, 0, 255), -1)

    window_name = "Detections"
    resized_image = cv.resize(frame, (1920, 1080), interpolation=cv.INTER_AREA)
    cv.namedWindow(window_name, cv.WINDOW_NORMAL)
    cv.setWindowProperty(window_name, cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)
    cv.imshow(window_name, resized_image)
    
    cv.waitKey(0)
    if cv.waitKey(1) & 0xFF == ord('q'):
        break
cv.destroyAllWindows()
