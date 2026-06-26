# Workspace Rules for win-translate

Chào mừng các AI Agent tham gia phát triển dự án **win-translate** (Phần mềm dịch game thời gian thực trên Windows 11). Dưới đây là các quy tắc, nguyên tắc thiết kế và cấu trúc dự án cần tuân thủ:

## Cấu trúc thư mục dự án
- `main.py`: File chạy khởi động ứng dụng.
- `main_window.py`: Giao diện điều khiển chính (chọn ngôn ngữ, tắt/bật, độ trong suốt).
- `selection_widget.py`: Công cụ vẽ vùng chọn màn hình cần dịch (semi-transparent overlay).
- `overlay_widget.py`: Khung hiển thị phụ đề dịch đè lên game (transparent click-through window).
- `ocr_engine.py`: Xử lý nhận dạng chữ từ ảnh chụp bằng Windows Media OCR API.
- `translator_thread.py`: Luồng chạy ngầm điều phối chụp màn hình -> OCR -> Dịch thuật -> Gửi tín hiệu cập nhật UI.
- `requirements.txt`: Các thư viện phụ thuộc.

## Nguyên tắc kỹ thuật & Quy chuẩn code

1. **Giao diện người dùng (PyQt6)**:
   - Sử dụng stylesheet hiện đại, giao diện tối (dark mode) mặc định để phù hợp với môi trường game.
   - Tất cả các tác vụ nặng (như chụp màn hình, OCR, dịch thuật) **bắt buộc** phải được thực hiện trong một luồng riêng (`QThread`) và giao tiếp với UI thông qua PyQt Signals (`pyqtSignal`). Không chạy trực tiếp trên main UI thread để tránh làm đơ giao diện.
   - Cửa sổ dịch (`OverlayWidget`) phải sử dụng các flag thích hợp của Windows để giữ thuộc tính luôn nằm trên cùng (Always on Top) và cho phép click xuyên qua (Click-through) khi ở chế độ dịch.

2. **Quy tắc cho Windows OCR**:
   - Sử dụng module `winrt.windows.media.ocr` thông qua Python.
   - Luôn kiểm tra xem ngôn ngữ nguồn đã được cài đặt trên hệ thống chưa trước khi khởi tạo `OcrEngine`.
   - Nếu chưa cài đặt, thông báo rõ ràng cho người dùng, tránh gây crash ClassFactory.

3. **Tối ưu hóa dịch thuật (Translation)**:
   - Chỉ gửi yêu cầu dịch khi văn bản sau OCR thực sự thay đổi hoặc khác biệt đáng kể (sử dụng khoảng cách Levenshtein hoặc so sánh chuỗi cơ bản).
   - Triển khai cơ chế caching cục bộ bằng một dictionary đơn giản để lưu trữ các câu đã dịch trước đó.
   - Thiết lập cơ chế fallback: nếu Google Translate trả về lỗi (ví dụ: HTTP 429), tự động chuyển sang dịch vụ dự phòng như MyMemory hoặc hiển thị thông báo lỗi nhẹ nhàng trên UI thay vì crash ứng dụng.
