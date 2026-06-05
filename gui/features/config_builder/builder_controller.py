# --- START OF FILE gui/features/config_builder/builder_controller.py ---

import os
from PyQt6.QtCore import QObject, pyqtSlot, QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QInputDialog
from PyQt6.QtGui import QIcon
import numpy as np
import cv2

# Import các Manager của tầng Core
from core.vehicle import VehicleManager
from core.engine import ViolationRuleEngine
from core.engine import (
    WrongWayRule, LineCrossingRule, WrongLaneRule, 
    RedLightRunningRule
)
from core.records import ViolationRecordManager
from core.lane import LaneManager, ZoneManager
from infrastructure.ai_adapters.yaml_mapper import YAML_ClassMapper
from infrastructure.evidence_writer import VideoRingBuffer
from infrastructure.evidence_generator import EvidenceGenerator
from infrastructure.visual_annotator import VisualAnnotator
# Import Services & Threads
from services.detection_service import DetectionService
from services.violation_service import ViolationService
from gui.features.config_builder.ai_vision_thread import AIVisionThread
from gui.features.config_builder.manager.workspace_manager import WorkspaceManager
from gui.features.config_builder.manager.config_compiler import ConfigCompiler
from gui.shared_components.event_broker import app_broker

from infrastructure.ai_adapters.alpr.plate_recognizer import LicensePlateRecognizer
from utils import paths

from logging import Logger

from gui.features.config_builder.components.lane_config_widget import LaneConfigWidget
from gui.features.config_builder.components.zone_config_widget import ZoneConfigWidget
from gui.features.config_builder.components.light_config_widget import LightConfigWidget
from gui.features.config_builder.components.lane_rule_config_widget import LaneRuleConfigWidget

class BuilderController(QObject):
    """
    Trình điều khiển trung tâm cho tính năng Thiết lập Cấu hình AI.
    Quản lý vòng đời (Lifecycle) của luồng AI và đồng bộ giao diện người dùng.
    """
    def __init__(self, canvas, panel, toolbar, db_service): 
        super().__init__()
        self.canvas = canvas
        self.panel = panel
        self.toolbar = toolbar
        self.db_service = db_service
        
        self.workspace_mgr = WorkspaceManager(panel, canvas)
        
        self._init_backend_services()
        
        self.compiler = ConfigCompiler(
            self.panel, 
            self.workspace_mgr, 
            self.lane_manager, 
            self.zone_manager,
            self.traffic_lights
        )

        self._load_cameras_to_ui()
        self._wire_signals()

    def _init_backend_services(self) -> None:
        """Khởi tạo toàn bộ bộ máy AI (Core + Services) với chuẩn mới"""
        self.vehicle_manager = VehicleManager()
        
        self.rule_engine = ViolationRuleEngine()
        self.rule_engine.add_rule(WrongWayRule())
        self.rule_engine.add_rule(LineCrossingRule())
        self.rule_engine.add_rule(WrongLaneRule())
        self.rule_engine.add_rule(RedLightRunningRule())

        self.record_manager = ViolationRecordManager()
        self.video_buffer = VideoRingBuffer() 
        self.evidence_generator = EvidenceGenerator() # [THÊM MỚI]: Khởi tạo Instance I/O Async
        
        self.lane_manager = LaneManager(lanes=[])
        self.zone_manager = ZoneManager(zones=[])
        self.traffic_lights = [] 

        self.class_mapper = YAML_ClassMapper(paths.YAML)
        
        # Mô hình OCR hiện tại đã bị cô lập ở tầng Service (Chờ mô hình mới)
        self.alpr_service = LicensePlateRecognizer(yolo_model_path=paths.LICENSE_PLATE_DETECTION_OPENVINO_MODEL)

        self.detection_service = DetectionService(self.class_mapper, self.vehicle_manager)
        
        # Tiêm các dịch vụ mới vào ViolationService
        self.violation_service = ViolationService(
            rule_engine=self.rule_engine, 
            record_manager=self.record_manager, 
            video_buffer=self.video_buffer,
            lane_manager=self.lane_manager, 
            zone_manager=self.zone_manager, 
            evidence_generator=self.evidence_generator, # Tiêm Evidence Async
            db_service=self.db_service,
            alpr_service=self.alpr_service 
        )

        self.video_thread = AIVisionThread(
            detection_service=self.detection_service, 
            violation_service=self.violation_service, 
            traffic_lights=self.traffic_lights,
            model_path=paths.VEHICLE_DETECTION_OPENVINO_MODEL
        )
        self.visual_annotator = VisualAnnotator()

    def _wire_signals(self) -> None:
        self.panel.media_load_requested.connect(self.handle_load_media)
        self.panel.play_pause_requested.connect(self.handle_play_pause)
        self.panel.seek_requested.connect(self.video_thread.seek_frame)
        self.panel.start_ai_requested.connect(self.handle_start_ai)

        self.panel.reset_requested.connect(self.handle_reset_workspace)
        self.panel.export_requested.connect(self.handle_export_json)
        
        self.video_thread.video_info_ready.connect(self.handle_video_info)
        self.video_thread.frame_processed.connect(self.handle_new_frame)
        self.video_thread.playback_finished.connect(self.handle_playback_finished)

        #self.panel.btn_add_cam.clicked.connect(self.handle_quick_add_camera)
        app_broker.toggle_db_logging.connect(self.handle_toggle_db)
        self.toolbar.annotator_config_changed.connect(
            self.visual_annotator.update_config
        )

        self.panel.import_requested.connect(self.handle_import_config)
    # =========================================================================
    # LOGIC MEDIA & AI (ĐÃ LOẠI BỎ CÁC ĐOẠN BLOCKING I/O)
    # =========================================================================
    
    @pyqtSlot(str)
    def handle_load_media(self, filepath: str) -> None:
        # [SỬA LỖI]: Không gọi wait_for_export_finish ở đây gây treo UI. 
        # Thread sẽ tự biết chờ khi ta gọi stop()
        self.video_thread.stop()
        self.video_thread.ai_enabled = False 
        self.video_thread.load_video(filepath)
        self.video_thread.start()
        
        QTimer.singleShot(50, self.canvas.recenter_and_fit)

    @pyqtSlot()
    def handle_play_pause(self) -> None:
        if not self.video_thread.cap or not self.video_thread.cap.isOpened(): 
            return
        self.video_thread.toggle_pause()
        if self.video_thread.is_paused:
            self.panel.btn_play.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "pause.png")))
        else:
            self.panel.btn_play.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "play.png")))

    @pyqtSlot(np.ndarray, list, object)
    def handle_new_frame(self, frame: np.ndarray, vehicles_list: list, tracked_detections: object) -> None:
        """Nhận frame từ AI Thread, vẽ đồ họa đè lên và cập nhật Canvas"""
        
        if frame is None:
            return

        is_grid_on = self.toolbar.btn_grid.isChecked()
        self.visual_annotator.config.is_enabled = is_grid_on

        current_registry = self.workspace_mgr.object_registry
        
        drawn_frame = self.visual_annotator.annotate(
            frame=frame, 
            vehicles=vehicles_list, 
            tracked_detections=tracked_detections, 
            registry=current_registry
        )
        
        final_frame = drawn_frame if drawn_frame is not None else frame
        
        self.canvas.set_frame(final_frame, [])
        
        if self.video_thread.cap:
            current_frame_idx = int(self.video_thread.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.panel.update_video_progress(current_frame_idx)
            
    @pyqtSlot(float, int)
    def handle_video_info(self, fps: float, total_frames: int) -> None:
        self.video_buffer.update_fps(fps)
        self.panel.update_video_info(fps, total_frames)

    @pyqtSlot()
    def handle_playback_finished(self) -> None:
        self.panel.btn_play.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "play.png")))

    @pyqtSlot()
    def handle_start_ai(self) -> None:
        camera_id = self.panel.combo_cam_select.currentData()
        if not camera_id:
            QMessageBox.critical(self.canvas, "Lỗi", "Vui lòng chọn hoặc thêm Camera trước khi chạy AI!")
            return

        success = self.compiler.compile()
        if not success: 
            return 
        
        camera_name = self.panel.combo_cam_select.currentText()
        self.record_manager.camera_name = camera_name 
        self.violation_service.current_camera_id = camera_id
           
        current_frame_idx = 0
        if self.video_thread.cap and self.video_thread.cap.isOpened():
            current_frame_idx = int(self.video_thread.cap.get(cv2.CAP_PROP_POS_FRAMES))

        self.video_thread.stop()
        self.video_thread.ai_enabled = True
        self.video_thread.load_video(self.video_thread.video_path)
        self.video_thread.seek_frame(current_frame_idx)
        self.video_thread.start()
        
        self.panel.btn_play.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "pause.png")))

        QMessageBox.information(self.canvas, "AI Ready", f"Hệ thống giám sát '{camera_name}' đã khởi động!")
    
    @pyqtSlot()
    def handle_reset_workspace(self) -> None:
        is_cleared = self.workspace_mgr.reset_workspace()
        if is_cleared:
            self.video_thread.stop()
            self.video_thread.video_path = ""
            self.panel.btn_play.setIcon(QIcon(os.path.join(paths.ICONS_DIR, "play.png")))
            self.panel.update_video_info(0, 0)
            self.panel.update_video_progress(0)

    @pyqtSlot(bool)
    def handle_toggle_db(self, is_enabled: bool) -> None:
        self.violation_service.enable_db_logging = is_enabled
        status_text = "ĐÃ BẬT" if is_enabled else "ĐÃ TẮT"
        #logger.info(f"[CONTROLLER] Chế độ lưu bằng chứng (DB & I/O): {status_text}")

    # =========================================================================
    # TƯƠNG TÁC VỚI DATABASE (SỬ DỤNG CONNECTION POOL)
    # =========================================================================

    def _load_cameras_to_ui(self, select_id: int = None) -> None:
        self.panel.combo_cam_select.blockSignals(True)
        self.panel.combo_cam_select.clear()
        
        cameras = self.db_service.cameras.get_all()
        if not cameras:
            self.panel.combo_cam_select.addItem("--- Chưa có Camera nào ---", userData=None)
        else:
            for cam in cameras:
                self.panel.combo_cam_select.addItem(cam['ten_camera'], userData=cam['id'])
                
            if select_id:
                index = self.panel.combo_cam_select.findData(select_id)
                if index >= 0:
                    self.panel.combo_cam_select.setCurrentIndex(index)
                    
        self.panel.combo_cam_select.blockSignals(False)

    @pyqtSlot()
    def handle_quick_add_camera(self) -> None:
        text, ok = QInputDialog.getText(
            self.canvas, 'Thêm Camera Mới', 
            'Nhập tên Camera (VD: CAM_NGA_TU_A):'
        )
        if ok and text.strip():
            cam_name = text.strip()
            new_id = self.db_service.cameras.add(ten_camera=cam_name)
            
            if new_id > 0:
                QMessageBox.information(self.canvas, "Thành công", f"Đã thêm Camera '{cam_name}' vào CSDL.")
                self._load_cameras_to_ui(select_id=new_id)
            else:
                QMessageBox.warning(self.canvas, "Lỗi", "Không thể thêm Camera. Tên này có thể đã tồn tại!")

    @pyqtSlot()
    def handle_export_json(self) -> None:
        camera_id = self.panel.combo_cam_select.currentData()
        camera_name = self.panel.combo_cam_select.currentText()
        if not camera_id:
            QMessageBox.critical(
                self.canvas, "Lỗi", 
                "Vui lòng chọn hoặc thêm Camera mới trước khi Xuất JSON."
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
                "bbox": [light.bbox[0], light.bbox[1], light.bbox[2], light.bbox[3]], 
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

        safe_cam_name = camera_name.replace(" ", "_")
        default_filename = f"config_{safe_cam_name}.json"

        filepath, _ = QFileDialog.getSaveFileName(
            self.canvas, "Lưu Cấu Hình AI", 
            os.path.join(default_dir, default_filename), # Tên tệp động
            "JSON Files (*.json);;All Files (*)" 
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, ensure_ascii=False, indent=4)

                self.db_service.cameras.update_config_path(camera_id, filepath)
                msg = f"Đã xuất cấu hình và liên kết với Camera ID: {camera_id}!"
                QMessageBox.information(self.canvas, "Thành công", msg)
            except Exception as e:
                QMessageBox.critical(self.canvas, "Lỗi", f"Không thể lưu file: {str(e)}")
    

    @pyqtSlot(int)
    def handle_import_config(self, camera_id: int):
        import json
        
        # 1. Truy vấn CSDL lấy đường dẫn
        cameras = self.db_service.cameras.get_all()
        cam_info = next((c for c in cameras if c['id'] == camera_id), None)
        
        if not cam_info or not cam_info.get('duong_dan_cau_hinh'):
            QMessageBox.warning(self.canvas, "Trống", "Camera này chưa được lưu cấu hình (JSON) nào!")
            return
            
        filepath = cam_info['duong_dan_cau_hinh']
        if not os.path.exists(filepath):
            QMessageBox.error(self.canvas, "Lỗi", f"Không tìm thấy tệp JSON tại: {filepath}")
            return

        # 2. Đọc JSON
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self.canvas, "Lỗi file", f"File JSON bị hỏng: {e}")
            return

        # 3. Yêu cầu Workspace Manager vẽ đồ họa lên Canvas
        self.workspace_mgr.decompile_graphics(json_data)

        # 4. Tái tạo các Thẻ Cấu Hình (UI Cards)
        self.panel._clear_all_cards() # Xóa UI cũ, tự động gọi reset_counters()
        self._decompile_ui_cards(json_data)
        
        # 5. Fit màn hình và báo cáo
        self.canvas.recenter_and_fit()
        
        # Đồng bộ với nút Grid Toolbar (Ẩn/Hiện ROIs theo tùy chọn hiện tại)
        is_rois_on = self.toolbar.current_annotator_config.show_rois
        app_broker.request_toggle_rois_visibility.emit(is_rois_on)
        
        QMessageBox.information(self.canvas, "Hoàn tất", "Đã tải cấu hình thành công!")
    
    def _decompile_ui_cards(self, json_data: dict):
        """Khôi phục các Thẻ Cấu Hình trên Right Panel"""
        registry = self.workspace_mgr.object_registry
        
        registry_data_for_ui = {
            "POLYGONS": list(registry["POLYGONS"].keys()),
            "BBOXES": list(registry["BBOXES"].keys()),
            "LINES": list(registry["LINES"].keys()),
            "RULES": [] # Khởi tạo rỗng, lát nữa sẽ add vào sau khi sinh thẻ Rule
        }
        
        # Từ điển lưu tạm ánh xạ: Lane JSON ID -> Auto Rule ID (VD: "Làn 1" -> "RULE_01")
        lane_rule_mapping = {}

        # ==================== 1. KHÔI PHỤC LANE RULES (TẠO THẺ THẬT) ====================
        for lane_data in json_data.get("lanes", []):
            allowed_names = lane_data.get("allowed_vehicles", [])
            lane_id = lane_data.get("id", "Unknown")
            
            rule_card = LaneRuleConfigWidget()
            
            allowed_enums = set()
            from utils.enums import TrafficVehicleType
            for name in allowed_names:
                try: 
                    # 1. Chuyển string JSON sang đối tượng Enum
                    enum_val = TrafficVehicleType[name]
                    allowed_enums.add(enum_val)
                    
                    # 2. Dùng code "Click" vào Checkbox (Dựa theo Tên Tiếng Việt: enum_val.value)
                    menu = rule_card.btn_vehicles.menu()
                    for action in menu.actions():
                        checkbox = action.defaultWidget()
                        if checkbox.text() == enum_val.value: # [CẬP NHẬT VÁ LỖI]: So sánh bằng Tiếng Việt
                            checkbox.setChecked(True)
                except KeyError: 
                    pass
            
            # 3. Lấy ID tự động vừa sinh của thẻ này (VD: "RULE_01")
            auto_rule_id = rule_card.input_id.text()
            
            # 4. Lưu ánh xạ để lát Lane móc vào
            lane_rule_mapping[lane_id] = auto_rule_id
            
            # 5. Ghi danh vào bộ nhớ Backend
            self.workspace_mgr.object_registry["RULES"][auto_rule_id] = set(rule_card.allowed_vehicles)
            
            # 6. Gắn UI
            rule_card.request_delete.connect(self.panel._remove_card)
            self.panel.object_list_layout.addWidget(rule_card)
        
        # Cập nhật danh sách RULES cho UI
        registry_data_for_ui["RULES"] = list(registry["RULES"].keys())
        self.workspace_mgr.broadcast_registry()

        # ==================== 2. KHÔI PHỤC LANES ====================
        for lane_data in json_data.get("lanes", []):
            card = LaneConfigWidget()
            
            # Bơm danh sách ID đồ họa & Rule
            card.update_registry_list(registry_data_for_ui)
            
            lane_id = lane_data.get("id", "")
            card.input_id.setText(lane_id)
            
            # [CẬP NHẬT]: Móc đúng vào Auto Rule ID vừa tạo ở Bước 1
            rule_id_to_select = lane_rule_mapping.get(lane_id)
            if rule_id_to_select:
                rule_idx = card.combo_rule_ref.findText(rule_id_to_select)
                if rule_idx >= 0: 
                    card.combo_rule_ref.setCurrentIndex(rule_idx)
            
            poly_id = lane_data.get("_mapped_poly_id")
            if poly_id:
                card.current_obj_id = poly_id
                poly_idx = card.combo_ref.findText(poly_id)
                if poly_idx >= 0: card.combo_ref.setCurrentIndex(poly_idx)
                
                card.build_sub_edges_ui(len(lane_data.get("edges", [])))
                for i, edge_info in enumerate(lane_data.get("edges", [])):
                    type_str = edge_info.get("type", "SOLID")
                    idx = card.sub_edge_combos[i].findData(type_str)
                    if idx >= 0: card.sub_edge_combos[i].setCurrentIndex(idx)
                    
            card.request_delete.connect(self.panel._remove_card)
            self.panel.object_list_layout.addWidget(card)

        # ==================== 3. KHÔI PHỤC ZONES ====================
        for zone_data in json_data.get("zones", []):
            card = ZoneConfigWidget()
            
            # [VÁ LỖI QUAN TRỌNG]
            card.update_registry_list(registry_data_for_ui)
            
            card.input_id.setText(zone_data.get("id", ""))
            
            type_idx = card.combo_type.findData(zone_data.get("type", "FORBIDDEN_AREA"))
            if type_idx >= 0: card.combo_type.setCurrentIndex(type_idx)
            
            hours = zone_data.get("prohibited_hours")
            if hours and len(hours) == 2:
                card.spin_start_hour.setValue(hours[0])
                card.spin_end_hour.setValue(hours[1])
            
            days = zone_data.get("prohibited_days")
            if days == "EVEN": card.combo_days.setCurrentIndex(1)
            elif days == "ODD": card.combo_days.setCurrentIndex(2)
            else: card.combo_days.setCurrentIndex(0)
            
            poly_id = zone_data.get("_mapped_poly_id")
            if poly_id:
                card.current_obj_id = poly_id
                poly_idx = card.combo_ref.findText(poly_id)
                if poly_idx >= 0: card.combo_ref.setCurrentIndex(poly_idx)
                
            card.request_delete.connect(self.panel._remove_card)
            self.panel.object_list_layout.addWidget(card)

        # ==================== 4. KHÔI PHỤC ĐÈN GIAO THÔNG ====================
        for light_data in json_data.get("traffic_lights", []):
            card = LightConfigWidget()
            
            # [VÁ LỖI QUAN TRỌNG]
            card.update_registry_list(registry_data_for_ui)
            
            card.input_id.setText(light_data.get("id", ""))
            
            bbox_id = light_data.get("_mapped_bbox_id")
            if bbox_id:
                card.current_bbox_id = bbox_id
                idx = card.combo_bbox.findText(bbox_id)
                if idx >= 0: card.combo_bbox.setCurrentIndex(idx)
                
            stop_id = light_data.get("_mapped_stop_id")
            if stop_id:
                card.current_stop_id = stop_id
                idx = card.combo_stop.findText(stop_id)
                if idx >= 0: card.combo_stop.setCurrentIndex(idx)

            right_id = light_data.get("_mapped_right_id")
            if right_id:
                card.current_right_id = right_id
                idx = card.combo_right.findText(right_id)
                if idx >= 0: card.combo_right.setCurrentIndex(idx)

            card.request_delete.connect(self.panel._remove_card)
            self.panel.object_list_layout.addWidget(card)
            
        self.panel.config_box.update_content_height()

# --- END OF FILE gui/features/config_builder/builder_controller.py ---