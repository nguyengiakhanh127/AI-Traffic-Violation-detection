import cv2
import threading
from collections import deque
import numpy as np
import logging
import os
import time # [THÊM IMPORT]
from queue import Queue, Full

logger = logging.getLogger("EvidenceWriter")

class VideoRingBuffer:
    def __init__(self, fps: int = 30, seconds: int = 10):
        self.fps = max(1, int(fps))
        self.seconds = seconds
        self.maxlen = self.fps * self.seconds

        self.buffer: deque = deque(maxlen=self.maxlen)
        self.frame_size = None

        self._lock = threading.Lock()

        self._export_queue = Queue(maxsize=50)

        self._worker_thread = threading.Thread(
            target=self._export_worker,
            name="EvidenceWriterWorker",
            daemon=True
        )
        self._worker_thread.start()

    def push(self, frame: np.ndarray) -> None:
        if self.frame_size is None:
            h, w = frame.shape[:2]
            self.frame_size = (w, h)

        success, encoded_image = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        
        if success:
            with self._lock:
                self.buffer.append(encoded_image.tobytes())

    def clear(self) -> None:
        with self._lock:
            self.buffer.clear()
            self.frame_size = None
            logger.info("🗑️ Đã giải phóng hoàn toàn bộ đệm Video.")

    def trigger_export(self, output_filepath: str) -> None:
        with self._lock:
            if len(self.buffer) == 0:
                logger.warning("Buffer trống, không thể xuất video.")
                return

            snapshot_jpeg_bytes = list(self.buffer)
            fps = self.fps
            frame_size = self.frame_size

        try:
            output_dir = os.path.dirname(output_filepath)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)

            self._export_queue.put_nowait(
                (snapshot_jpeg_bytes, output_filepath, fps, frame_size)
            )
            logger.info(f"📥 Đã đưa yêu cầu xuất video vào hàng đợi: {output_filepath}")

        except Full:
            logger.warning(f"⚠️ Hàng đợi Export đã đầy! Video {output_filepath} bị bỏ qua.")
        except Exception as e:
            logger.error(f"❌ Lỗi khi khởi tạo thư mục xuất: {e}")

    def _export_worker(self):
        logger.info("🚀 Luồng Export nền đã khởi động.")
        while True:
            task = self._export_queue.get()
            try:
                jpeg_bytes_list, filepath, fps, size = task
                self._write_video_task(jpeg_bytes_list, filepath, fps, size)
            except Exception as e:
                logger.exception(f"❌ Worker export bị lỗi đột ngột, bỏ qua tệp này: {e}")
            finally:
                self._export_queue.task_done()
                time.sleep(0.5)

    def _write_video_task(self, jpeg_bytes_list, filepath: str, fps: int, size: tuple) -> None:
        out = None
        try:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
            
            out = cv2.VideoWriter(filepath, fourcc, float(fps), size)
            
            if not out.isOpened():
                raise RuntimeError(f"Không mở được luồng VideoWriter: {filepath}")

            for jpeg_bytes in jpeg_bytes_list:
                np_arr = np.frombuffer(jpeg_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                if frame is not None:
                    out.write(frame)
                    
        except Exception as e:
            logger.error(f"❌ Lỗi ghi video {filepath}: {e}")
            if os.path.exists(filepath):
                try: os.remove(filepath)
                except: pass
        finally:
            if out is not None:
                out.release()
                logger.info(f"✅ Đã đóng và lưu tệp video an toàn: {filepath}")

    def update_fps(self, new_fps: float) -> None:
        with self._lock:
            self.fps = max(1, int(new_fps))
            self.maxlen = self.fps * self.seconds
            self.buffer = deque(self.buffer, maxlen=self.maxlen)
    
    def wait_for_export_finish(self, timeout_sec: int = 10) -> None:
        if self._export_queue.unfinished_tasks > 0:
            logger.info(f"⏳ Đang chờ hệ thống ghi nốt {self._export_queue.unfinished_tasks} video bằng chứng còn lại...")
            
            # Khởi tạo bộ đếm thời gian tránh bị treo vĩnh viễn
            start_time = time.time()
            while self._export_queue.unfinished_tasks > 0:
                if time.time() - start_time > timeout_sec:
                    logger.warning("⚠️ Quá thời gian chờ (Timeout). Buộc dừng xuất video.")
                    break
                time.sleep(0.5) # Ngủ 0.5s rồi check lại
                
            if self._export_queue.unfinished_tasks == 0:
                logger.info("✅ Đã ghi xong toàn bộ bằng chứng. Sẵn sàng tắt.")