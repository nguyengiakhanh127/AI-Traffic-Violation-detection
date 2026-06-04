import os

"""
    Tệp này phụ  trách quản lý và giúp các tệp khác dễ dàng điều phối đường dẫn
"""
# Tự động tìm gốc của dự án (Thư mục cha của /utils)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tầng Giao diện (Assets)
ICONS_DIR = os.path.join(PROJECT_ROOT, "gui", "assets", "icons")
CURSORS_DIR = os.path.join(PROJECT_ROOT, "gui", "assets", "cursors")

# Tầng Dữ liệu (Data)
CONFIGS_DIR = os.path.join(PROJECT_ROOT, "data", "configs")

VEHICLE_DETECTION_STANDARD_MODEL = os.path.join(PROJECT_ROOT, r"model\yolo\standard_format\vehicle_detection\best.pt") 
VEHICLE_DETECTION_OPENVINO_MODEL = os.path.join(PROJECT_ROOT, r"model\yolo\openVINO_format\vehicle_detection\best_openvino_model")

YAML = os.path.join(PROJECT_ROOT, r"model\yaml\hutech.yaml") 

LICENSE_PLATE_DETECTION_OPENVINO_MODEL = os.path.join(PROJECT_ROOT, r"license-plate-finetune-v1x.pt")

EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "Evidence")
# --- END OF FILE utils/paths.py ---