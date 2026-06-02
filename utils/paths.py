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
MODEL_DIR = os.path.join(PROJECT_ROOT, "yolo26n_openvino_model") # OPEN VINO
EVIDENCE_DIR = os.path.join(PROJECT_ROOT, "Evidence")
# --- END OF FILE utils/paths.py ---