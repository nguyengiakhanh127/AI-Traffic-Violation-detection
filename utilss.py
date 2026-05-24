import os
import cv2 as cv
import numpy as np
from moviepy.video.io.VideoFileClip import VideoFileClip
from typing import Optional
import supervision as sv
def extract_first_minute(
        input_video_path: str,
        output_video_path: str,
        minute: int = 60
)-> None:
    with VideoFileClip(input_video_path) as video:
        if video.duration < 60:
            clip_to_save = video
        else:
            clip_to_save = video.subclipped(30, minute)
        clip_to_save.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
        video.close()

def select_lane_roi(
        image_path: Optional[str],
        image: Optional[np.ndarray]
) -> list[tuple[int, int]]:
    """
    Khởi tạo một cửa sổ tương tác cho phép người dùng click chuột để vẽ và xác định các đỉnh của một đa giác (Làn đường).
    
    Quy trình hoạt động:
    1. Đọc ảnh từ đường dẫn được cung cấp. Nếu ảnh không tồn tại, trả về danh sách rỗng.
    2. Mở một cửa sổ hiển thị hình ảnh với tên "ROI Selector".
    3. Người dùng sử dụng Chuột Trái (Left Click) để đánh dấu các đỉnh của đa giác.
    4. Trực quan hóa hành vi: Tại mỗi vị trí click, một điểm tròn màu đỏ sẽ được vẽ lên. Khi có từ 2 điểm trở lên, một đường thẳng màu xanh lá sẽ tự động nối các điểm lại với nhau để định hình cạnh của đa giác.
    5. Tính năng Hoàn tác (Undo): Người dùng có thể nhấn phím 'z' hoặc phím Backspace (mã 8) để xóa bỏ điểm vừa click gần nhất. Màn hình sẽ tự động vẽ lại trạng thái trước đó.
    6. Vòng lặp sẽ duy trì trạng thái chờ thao tác từ người dùng.
    7. Người dùng nhấn phím Enter (mã 13) hoặc phím Space (mã 32) để xác nhận kết thúc việc vẽ.
    8. Cửa sổ đóng lại và hàm trả về tập hợp các tọa độ (x, y) đã chọn dưới dạng list of tuples.
    """
    if image is None:
        image = cv.imread(image_path)

    if image is None:
        #raise FileNotFoundError(f"{image_path} not exist.")
        return []
    print(f"Thông tin ảnh: {image.shape}")
    result = []
    clone = image.copy()
    window_name = "ROI Selector"
     
    def redraw():
        nonlocal clone
        clone = image.copy()
        for i, pt in enumerate(result):
            cv.circle(clone, pt, 5, (0, 0, 255), -1)
            if i > 0:
                cv.line(clone, result[i-1], pt, (0, 255, 0), 2)
        cv.imshow(window_name, clone)

    def mouse_callback(event, x, y, flags, param):
        if event == cv.EVENT_LBUTTONDOWN:
            result.append((x, y))
            redraw()

    cv.namedWindow(window_name, cv.WINDOW_NORMAL)
    cv.setWindowProperty(window_name, cv.WND_PROP_FULLSCREEN, cv.WINDOW_FULLSCREEN)
    cv.setMouseCallback(window_name, mouse_callback)
    redraw()

    while True:
        key = cv.waitKey(1) & 0xFF
        if key == 13 or key == 32:
            break
        elif key == ord('z') or key == 8:
            if len(result) > 0:
                result.pop()
                redraw()

    cv.destroyAllWindows()
    return result

if __name__ == "__main__":     
    print(select_lane_roi(
        image_path= r"demo_data\imgs\giao_thong_noi_do_tq_anh.jpg",
        image= None
    ))





