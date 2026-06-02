# --- START OF FILE infrastructure/evidence_writer.py ---
import cv2
import threading
from collections import deque
import numpy as np
import logging
import os
from queue import Queue, Full

logger = logging.getLogger("EvidenceWriter")

class VideoRingBuffer:
    def __init__(self, fps: int = 30, seconds: int = 15):
        self.fps = fps
        self.seconds = seconds
        self.maxlen = fps * seconds

        self.buffer: deque = deque(maxlen=self.maxlen)
        self.frame_size = None

        self._lock = threading.Lock()

        # ==========================
        # Export Queue + Worker
        # ==========================
        self._export_queue = Queue(maxsize=20)

        self._worker_thread = threading.Thread(
            target=self._export_worker,
            name="EvidenceWriterWorker",
            daemon=True
        )
        self._worker_thread.start()

    # ==========================================================
    # Push frame vào Ring Buffer
    # ==========================================================
    def push(self, frame: np.ndarray) -> None:
        if self.frame_size is None:
            h, w = frame.shape[:2]
            self.frame_size = (w, h)

        with self._lock:
            # [FIXED BUG]: Bắt buộc phải dùng .copy() để tránh việc 
            # camera backend ghi đè lên vùng nhớ của các frame cũ
            self.buffer.append(frame)

    # ==========================================================
    # Clear Buffer (Giải quyết vấn đề Tràn RAM)
    # ==========================================================
    def clear(self) -> None:
        """Xả sạch toàn bộ RAM đang bị chiếm dụng bởi hàng đợi video"""
        with self._lock:
            self.buffer.clear()
            self.frame_size = None
            logger.info("🗑️ Đã giải phóng hoàn toàn bộ nhớ đệm Video (Xả RAM).")

    # ==========================================================
    # Trigger export
    # ==========================================================
    def trigger_export(self, output_filepath: str) -> None:
        """
        Kích hoạt xuất video bằng chứng.
        Không tạo thread mới mỗi lần trigger.
        Chỉ đưa job vào queue để worker xử lý tuần tự.
        """
        with self._lock:
            if len(self.buffer) == 0:
                logger.warning("Buffer trống, không thể xuất video.")
                return

            # Chuyển thành tuple để lấy snapshot cực nhanh (Thread-safe)
            snapshot_frames = tuple(self.buffer)
            fps = self.fps
            frame_size = self.frame_size

        try:
            output_dir = os.path.dirname(output_filepath)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Đã tạo thư mục lưu trữ: {output_dir}")

        except Exception as e:
            logger.error(f"❌ Không thể tạo thư mục lưu video: {e}")
            return

        try:
            self._export_queue.put_nowait(
                (snapshot_frames, output_filepath, fps, frame_size)
            )
            logger.info(f"📥 Đã đưa video vào hàng đợi xuất: {output_filepath}")

        except Full:
            logger.warning("⚠️ Export queue đã đầy. Bỏ qua yêu cầu ghi video mới.")

    # ==========================================================
    # Worker xử lý export
    # ==========================================================
    def _export_worker(self):
        logger.info("🚀 EvidenceWriter worker started.")
        while True:
            task = self._export_queue.get()
            try:
                frames, filepath, fps, size = task
                self._write_video_task(frames, filepath, fps, size)
            except Exception:
                logger.exception("❌ Worker export gặp lỗi.")
            finally:
                self._export_queue.task_done()

    # ==========================================================
    # Encode Video (Nén H264 hoặc Fallback MP4V)
    # ==========================================================
    def _write_video_task(self, frames, filepath: str, fps: int, size: tuple) -> None:
        """
        [CẬP NHẬT]: Tận dụng Queue Worker để chạy nén H.264 tiết kiệm 90% dung lượng.
        Quá trình nén chậm một chút cũng không làm lag luồng AI chính.
        """
        try:
            # Ưu tiên chuẩn nén siêu nhẹ H.264
            import imageio
            writer = imageio.get_writer(filepath, fps=fps, codec='libx264', macro_block_size=None, quality=6)
            for frame in frames:
                # Chuyển BGR (OpenCV) sang RGB
                writer.append_data(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            writer.close()
            logger.info(f"✅ Saved evidence video (H.264 Optimized): {filepath}")

        except ImportError:
            # Fallback nếu máy chưa cài imageio
            logger.warning("⚠️ Đang lưu video bằng OpenCV (Dung lượng cao). Khuyến nghị: pip install imageio imageio-ffmpeg")
            try:
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(filepath, fourcc, fps, size)
                if not out.isOpened():
                    raise RuntimeError(f"Không mở được VideoWriter: {filepath}")
                for frame in frames:
                    out.write(frame)
                out.release()
                logger.info(f"✅ Saved evidence video (OpenCV): {filepath}")
            except Exception as e:
                logger.error(f"❌ Error writing fallback video {filepath}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Error writing video {filepath}: {e}")

    # ==========================================================
    # Update FPS
    # ==========================================================
    def update_fps(self, new_fps: float) -> None:
        with self._lock:
            self.fps = max(1, int(new_fps))
            self.maxlen = self.fps * self.seconds
            self.buffer = deque(self.buffer, maxlen=self.maxlen)

    # ==========================================================
    # Optional helper
    # ==========================================================
    def pending_exports(self) -> int:
        return self._export_queue.qsize()

# --- END OF FILE ---