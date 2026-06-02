from ultralytics import YOLO

model = YOLO("yolo26n_openvino_model")

print(model.names[3])