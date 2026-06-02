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

def detect_traffic_light_color(frame_source, roi_coords):
    """Trích xuất ROI đèn giao thông và xác định màu (Đỏ, Vàng, Xanh).

    roi_coords: Tuple kiểu (x, y, w, h) xác định vị trí đèn trong ảnh gốc.
    """
    x, y, w, h = roi_coords

    # 1. Cắt vùng ROI từ ảnh gốc
    roi = frame_source[y : y + h, x : x + w]

    # Kiểm tra nếu ROI trống (do tọa độ ngoài phạm vi ảnh)
    if roi.size == 0:
        return "Unknown (Invalid ROI)", None

    # 2. Xử lý tiền lọc nhiễu (Dùng Gaussian Blur để làm mờ, giảm nhiễu hạt)
    # Vì vật thể ở xa nên kernel size nhỏ (3x3 hoặc 5x5) là tối ưu
    blurred_roi = cv.GaussianBlur(roi, (3, 3), 0)

    # 3. Chuyển đổi sang không gian màu HSV
    hsv = cv.cvtColor(blurred_roi, cv.COLOR_BGR2HSV)
    # 4. Định nghĩa dải màu (Thêm biên độ rộng để bù đắp nhiễu sáng/vật thể xa)
    # Màu Đỏ nằm ở 2 dải trong OpenCV (Đầu và cuối trục Hue)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([165, 50, 50])
    upper_red2 = np.array([180, 255, 255])

    # Màu Vàng
    lower_yellow = np.array([11, 40, 50])
    upper_yellow = np.array([34, 255, 255])

    # Màu Xanh lá (Mở rộng dải xanh để bao gồm cả xanh ngọc/xanh biển nhạt của đèn led)
    lower_green = np.array([35, 40, 50])
    upper_green = np.array([95, 255, 255])

    # 5. Tạo mặt nạ lọc màu (Masking)
    mask_red = cv.bitwise_or(
        cv.inRange(hsv, lower_red1, upper_red1),
        cv.inRange(hsv, lower_red2, upper_red2),
    )
    mask_yellow = cv.inRange(hsv, lower_yellow, upper_yellow)
    mask_green = cv.inRange(hsv, lower_green, upper_green)

    # 6. Đếm số lượng pixel sáng trong mỗi mặt nạ màu
    red_pixels = cv.countNonZero(mask_red)
    yellow_pixels = cv.countNonZero(mask_yellow)
    green_pixels = cv.countNonZero(mask_green)

    # Đặt một ngưỡng tối thiểu (Threshold) để tránh nhận diện nhầm nhiễu nền
    # Ví dụ: Màu đó phải chiếm ít nhất 5% diện tích vùng ROI
    min_pixels_threshold = int(0.05 * (w * h))

    # 7. Biện luận đưa ra kết quả màu chiếm ưu thế nhất
    pixel_counts = {
        "RED": red_pixels,
        "YELLOW": yellow_pixels,
        "GREEN": green_pixels,
    }
    print(pixel_counts)
    detected_color = "UNKNOWN"
    max_pixels = max(pixel_counts.values())

    detected_color = max(pixel_counts, key=pixel_counts.get)

    return detected_color, roi

if __name__ == "__main__":     
    print(select_lane_roi(
        image_path=r"demo_data\imgs\vietnam_urban_traffic_HN.jpg",
        image= None
    ))





