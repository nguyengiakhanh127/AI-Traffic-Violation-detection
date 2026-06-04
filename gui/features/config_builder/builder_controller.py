from PyQt6.QtCore import QObject, pyqtSlot, QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
import cv2
import numpy as np
import os
import sys

# Import các Manager của tầng Core
from core.vehicle import VehicleManager
from core.engine import ViolationRuleEngine
from core.engine import (
    WrongWayRule, LineCrossingRule, WrongLaneRule, 
    IllegalParkingRule, PedestrianStopRule, RedLightRunningRule
)
from core.records import ViolationRecordManager
from core.lane import LaneManager, ZoneManager
from infrastructure.ai_adapters.yaml_mapper import YAML_ClassMapper
from infrastructure.evidence_writer import VideoRingBuffer

# Import Services & Threads
from services.detection_service import DetectionService
from services.violation_service import ViolationService
from gui.features.config_builder.ai_vision_thread import AIVisionThread
from gui.features.config_builder.manager.workspace_manager import WorkspaceManager
from gui.features.config_builder.manager.config_compiler import ConfigCompiler
from gui.shared_components.event_broker import app_broker

from infrastructure.ai_adapters.alpr.plate_recognizer import LicensePlateRecognizer

from utils import paths

class BuilderController(QObject):
    def __init__(self, canvas, panel, toolbar, db_service): 
        super().__init__()
        self.canvas = canvas
        self.panel = panel
        self.toolbar = toolbar
        self.db_service = db_service
        
        # 1. KHỞI TẠO QUẢN LÝ ĐỒ HỌA
        self.workspace_mgr = WorkspaceManager(panel, canvas)

        # 2. KHỞI TẠO HỆ THỐNG BACKEND AI
        project_root = os.path.dirname(os.path.abspath(__file__))
        self.vehicle_manager = VehicleManager()
        
        self.rule_engine = ViolationRuleEngine()
        self.rule_engine = ViolationRuleEngine()
        self.rule_engine.add_rule(WrongWayRule())
        self.rule_engine.add_rule(LineCrossingRule())
        self.rule_engine.add_rule(WrongLaneRule())
        self.rule_engine.add_rule(RedLightRunningRule())

        self.record_manager = ViolationRecordManager()
        self.video_buffer = VideoRingBuffer() 
        
        self.lane_manager = LaneManager(lanes=[])
        self.zone_manager = ZoneManager(zones=[])
        self.traffic_lights = [] 

        yaml_path = paths.YAML
        self.class_mapper = YAML_ClassMapper(yaml_path)
        
        license_plate_model_path = paths.LICENSE_PLATE_DETECTION_OPENVINO_MODEL
        self.alpr_service = LicensePlateRecognizer(yolo_model_path=license_plate_model_path)

        self.detection_service = DetectionService(self.class_mapper, self.vehicle_manager)
        self.violation_service = ViolationService(
            self.rule_engine, self.record_manager, self.video_buffer,
            self.lane_manager, self.zone_manager, self.db_service,
            alpr_service=self.alpr_service 
        )

        model_path = paths.VEHICLE_DETECTION_OPENVINO_MODEL
        self.video_thread = AIVisionThread(
            self.detection_service, self.violation_service, model_path=model_path,
            traffic_lights= self.traffic_lights
        )

        # 3. KHỞI TẠO TRÌNH BIÊN DỊCH
        self.compiler = ConfigCompiler(
            self.panel, 
            self.workspace_mgr, 
            self.lane_manager, 
            self.zone_manager,
            self.traffic_lights
        )

        self._load_cameras_to_ui()

        # 4. Nối dây tín hiệu
        self._wire_signals()

    def _wire_signals(self):
        self.panel.media_load_requested.connect(self.handle_load_media)
        self.panel.play_pause_requested.connect(self.handle_play_pause)
        self.panel.seek_requested.connect(self.video_thread.seek_frame)
        self.panel.start_ai_requested.connect(self.handle_start_ai)

        self.panel.reset_requested.connect(self.handle_reset_workspace)
        self.panel.export_requested.connect(self.handle_export_json)
        
        self.video_thread.video_info_ready.connect(self.handle_video_info)
        self.video_thread.frame_processed.connect(self.handle_new_frame)
        self.video_thread.playback_finished.connect(self.handle_playback_finished)

        self.panel.btn_add_cam.clicked.connect(self.handle_quick_add_camera)
        app_broker.toggle_db_logging.connect(self.handle_toggle_db)

    # =========================================================================
    # LOGIC MEDIA & AI
    # =========================================================================
    
    @pyqtSlot(str)
    def handle_load_media(self, filepath: str):
        # [CẬP NHẬT 2.1]: Ép chờ xuất nốt video cũ trước khi load video mới
        if self.video_thread.is_playing and self.violation_service.enable_db_logging:
            self.video_buffer.wait_for_export_finish(timeout_sec=10)
            
        self.video_thread.stop()
        self.video_thread.ai_enabled = False 
        self.video_thread.load_video(filepath)
        self.video_thread.start()
        
        self.panel.btn_play.setText("⏸")
        self.panel.btn_play.setStyleSheet("background-color: #d9534f; border-radius: 3px;") 
        QTimer.singleShot(50, self.canvas.recenter_and_fit)

    @pyqtSlot()
    def handle_play_pause(self):
        if not self.video_thread.cap or not self.video_thread.cap.isOpened(): return
        self.video_thread.toggle_pause()
        if self.video_thread.is_paused:
            self.panel.btn_play.setText("▶") 
            self.panel.btn_play.setStyleSheet("background-color: #007acc; border-radius: 3px;") 
        else:
            self.panel.btn_play.setText("⏸") 
            self.panel.btn_play.setStyleSheet("background-color: #d9534f; border-radius: 3px;") 

    @pyqtSlot(np.ndarray, list, object)
    def handle_new_frame(self, frame: np.ndarray, vehicles_list: list, tracked_detections: object):
        if self.toolbar.btn_grid.isChecked():
            self.canvas.set_frame(frame, vehicles_list)
        else:
            self.canvas.set_frame(frame, [])
        
        if self.video_thread.cap:
            current_frame_idx = int(self.video_thread.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.panel.update_video_progress(current_frame_idx)
            
    @pyqtSlot(float, int)
    def handle_video_info(self, fps: float, total_frames: int):
        self.video_buffer.update_fps(fps)
        self.panel.update_video_info(fps, total_frames)

    @pyqtSlot()
    def handle_playback_finished(self):
        self.panel.btn_play.setText("▶")
        self.panel.btn_play.setStyleSheet("background-color: #007acc; border-radius: 3px;")

    @pyqtSlot()
    def handle_start_ai(self):
        camera_id = self.panel.combo_cam_select.currentData()
        if not camera_id:
            QMessageBox.critical(self.canvas, "Lỗi", "Vui lòng chọn hoặc thêm Camera trước khi chạy AI!")
            return

        success = self.compiler.compile()
        if not success: return 
        
        # [CẬP NHẬT 1]: Cập nhật tên Camera thực tế cho RecordManager để tạo đúng Folder
        camera_name = self.panel.combo_cam_select.currentText()
        self.record_manager.camera_name = camera_name # Gán đè cái tên mặc định
        
        # Bơm ID của Camera đang chạy vào Service để lưu DB
        self.violation_service.current_camera_id = camera_id
           
        current_frame_idx = 0
        if self.video_thread.cap and self.video_thread.cap.isOpened():
            current_frame_idx = int(self.video_thread.cap.get(cv2.CAP_PROP_POS_FRAMES))

        self.video_thread.stop()
        self.video_thread.ai_enabled = True
        self.video_thread.load_video(self.video_thread.video_path)
        self.video_thread.seek_frame(current_frame_idx)
        self.video_thread.start()
        
        self.panel.btn_play.setText("⏸")
        self.panel.btn_play.setStyleSheet("background-color: #d9534f; border-radius: 3px;")
        QMessageBox.information(self.canvas, "AI Ready", f"Hệ thống AI giám sát '{camera_name}' đã khởi động!")
    
    @pyqtSlot()
    def handle_reset_workspace(self):
        is_cleared = self.workspace_mgr.reset_workspace()
        if is_cleared:
            # [CẬP NHẬT 2.2]: Chờ xuất video trước khi xóa trắng dữ liệu
            if self.video_thread.is_playing and self.violation_service.enable_db_logging:
                self.video_buffer.wait_for_export_finish(timeout_sec=10)
                
            self.video_thread.stop()
            self.video_thread.video_path = ""
            self.panel.btn_play.setText("▶")
            self.panel.btn_play.setStyleSheet("background-color: #007acc; border-radius: 3px;")
            self.panel.update_video_info(0, 0)
            self.panel.update_video_progress(0)
    @pyqtSlot(bool)
    def handle_toggle_db(self, is_enabled: bool):
        self.violation_service.enable_db_logging = is_enabled
        status_text = "ĐÃ BẬT" if is_enabled else "ĐÃ TẮT"
        print(f"[CONTROLLER] Chế độ lưu bằng chứng vào Ổ cứng/DB: {status_text}")


    # =========================================================================
    # TƯƠNG TÁC VỚI DATABASE (CẬP NHẬT KIẾN TRÚC MỚI)
    # =========================================================================

    def _load_cameras_to_ui(self, select_id: int = None):
        """[CẬP NHẬT]: Dùng db.cameras.get_all() thay vì db.get_all_cameras()"""
        self.panel.combo_cam_select.blockSignals(True)
        self.panel.combo_cam_select.clear()
        
        # Gọi thẳng vào Repository của Camera
        cameras = self.db_service.cameras.get_all()
        if not cameras:
            self.panel.combo_cam_select.addItem("--- Chưa có Camera nào ---", userData=None)
        else:
            for cam in cameras:
                # Thuộc tính Tiếng Việt: 'ten_camera' và 'id'
                self.panel.combo_cam_select.addItem(cam['ten_camera'], userData=cam['id'])
                
            if select_id:
                index = self.panel.combo_cam_select.findData(select_id)
                if index >= 0:
                    self.panel.combo_cam_select.setCurrentIndex(index)
                    
        self.panel.combo_cam_select.blockSignals(False)

    @pyqtSlot()
    def handle_quick_add_camera(self):
        """[CẬP NHẬT]: Dùng db.cameras.add()"""
        text, ok = QInputDialog.getText(
            self.canvas, 'Thêm Camera Mới', 
            'Nhập tên Camera (VD: CAM_NGA_TU_A):'
        )
        if ok and text.strip():
            cam_name = text.strip()
            
            # Gọi DB thêm mới (Hỗ trợ cấu trúc Tiếng Việt)
            new_id = self.db_service.cameras.add(ten_camera=cam_name)
            
            if new_id > 0:
                QMessageBox.information(self.canvas, "Thành công", f"Đã thêm Camera '{cam_name}' vào CSDL.")
                self._load_cameras_to_ui(select_id=new_id)
            else:
                QMessageBox.warning(self.canvas, "Lỗi", "Không thể thêm Camera. Tên này có thể đã tồn tại!")

    @pyqtSlot()
    def handle_export_json(self):
        camera_id = self.panel.combo_cam_select.currentData()
        if not camera_id:
            QMessageBox.critical(
                self.canvas, "Lỗi Nghiệp Vụ", 
                "Hệ thống không biết sẽ gắn cấu hình này cho Camera nào!\n\n"
                "Vui lòng ấn nút [+] để thêm Camera mới trước khi Xuất JSON."
            )
            return
        
        success = self.compiler.compile()
        if not success: return 

        config_data = {"lanes": [], "zones": [], "traffic_lights": []}

        for lane in self.lane_manager.lanes:
            config_data["lanes"].append({
                "id": lane.lane_id,
                "allowed_vehicles": [v.name for v in lane.lane_rule.allowed_vehicles],
                "edges": [{"p1": [e.p1.x, e.p1.y], "p2": [e.p2.x, e.p2.y], "type": e.line_type.name} for e in lane.edges]
            })

        for zone in self.zone_manager.zones:
            config_data["zones"].append({
                "id": zone.zone_id,
                "type": zone.zone_type.name,
                "prohibited_hours": list(zone.prohibited_hours) if zone.prohibited_hours else None,
                "prohibited_days": zone.prohibited_days,
                "vertices": [[v.x, v.y] for v in zone.polygon.vertices]
            })

        for light in self.traffic_lights:
            light_dict = {
                "id": light.light_id,
                "bbox": [light.bbox[0], light.bbox[1], light.bbox[2], light.bbox[3]], # xmin, ymin, xmax, ymax
                "stop_line": {"p1": [light.stop_line.p1.x, light.stop_line.p1.y], "p2": [light.stop_line.p2.x, light.stop_line.p2.y]},
            }

            if light.right_turn_line:
                light_dict["right_turn_line"] = {"p1": [light.right_turn_line.p1.x, light.right_turn_line.p1.y], "p2": [light.right_turn_line.p2.x, light.right_turn_line.p2.y]}
            else:
                light_dict["right_turn_line"] = None
                
            config_data["traffic_lights"].append(light_dict)

        import json
        default_dir = os.path.join(paths.PROJECT_ROOT, "data", "configs")
        os.makedirs(default_dir, exist_ok=True) 

        filepath, _ = QFileDialog.getSaveFileName(
            self.canvas, "Lưu Cấu Hình AI", 
            os.path.join(default_dir, "camera_config.json"), 
            "JSON Files (*.json);;All Files (*)" 
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=4)

                camera_id = self.panel.combo_cam_select.currentData()
                if camera_id:
                    # [THÊM TÍNH NĂNG]: Cập nhật đường dẫn file Config vào Database Camera
                    self.db_service.cameras.update_config_path(camera_id, filepath)
                    msg = f"Đã xuất cấu hình và liên kết thành công với Camera ID: {camera_id}!"
                else:
                    msg = f"Đã xuất cấu hình thành công tại:\n{filepath}\n(Chưa liên kết với Camera nào)"
                    
                QMessageBox.information(self.canvas, "Thành công", msg)
            except Exception as e:
                QMessageBox.critical(self.canvas, "Lỗi lưu file", f"Không thể lưu file: {str(e)}")