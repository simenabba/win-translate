# Win-Translate

**Win-Translate** là một phần mềm dịch trực tiếp màn hình game trong thời gian thực dành cho hệ điều hành Windows 10/11. Phần mềm được thiết kế tối ưu cho game thủ chơi các tựa game tiếng Anh hoặc tiếng Nhật (hoặc bất kỳ ngôn ngữ nào khác) có nhu cầu dịch nhanh phụ đề/lời thoại sang tiếng Việt trực tiếp trên màn hình mà không cần chuyển đổi cửa sổ.

---

## ✨ Các tính năng nổi bật

*   **Offline Windows OCR**: Nhận dạng chữ trực tiếp bằng công cụ Windows native OCR API tích hợp sẵn trong Windows 11. Tốc độ nhận diện siêu nhanh, chính xác cao và chạy offline hoàn toàn (không cần kết nối internet cho tính năng OCR).
*   **Overlay trong suốt & Click-Through**: Khung hiển thị chữ dịch (phụ đề) dạng Netflix, có viền bóng chữ giúp dễ đọc trên mọi nền game. Khi dịch, khung chữ sẽ được khóa và chuột có thể click xuyên qua (click-through) để bạn điều khiển game bình thường.
*   **Công cụ chọn vùng trực quan (Selection Tool)**: Cho phép kéo thả vẽ một khung hình chữ nhật bất kỳ trên màn hình (nơi xuất hiện lời thoại game) để phần mềm theo dõi và quét chữ.
*   **Chống chặn IP & Caching**: Tự động lưu bộ đệm các câu đã dịch để tránh gửi các yêu cầu dịch trùng lặp. Tích hợp cơ chế tự động chuyển đổi dự phòng (fallback) giữa các dịch vụ dịch như Google Translate và MyMemory Translate.
*   **Bảng điều khiển hiện đại**: Giao diện Control Panel giao diện tối (Dark Mode) cao cấp, dễ dàng tinh chỉnh kích cỡ chữ phụ đề, độ trong suốt của nền, tần suất dịch và ngôn ngữ.
*   **Đóng gói tự động**: Đi kèm script đóng gói tạo file `.exe` chạy độc lập chỉ với một dòng lệnh.

---

## 🛠️ Yêu cầu hệ thống

1.  **Hệ điều hành**: Windows 10 hoặc Windows 11.
2.  **Ngôn ngữ OCR trên Windows**: Máy tính của bạn **bắt buộc** phải cài đặt gói ngôn ngữ (Language Pack) tương ứng với ngôn ngữ game bạn muốn dịch (ví dụ: Tiếng Nhật hoặc Tiếng Anh).
    *   *Cách cài đặt*: Vào **Settings (Cài đặt) -> Time & Language (Thời gian & Ngôn ngữ) -> Language & Region (Ngôn ngữ & Vùng) -> Add a language (Thêm ngôn ngữ)** -> Tìm ngôn ngữ cần cài và đảm bảo chọn mục **Optical Character Recognition (OCR)** khi tải về.

---

## 🚀 Hướng dẫn cài đặt và chạy từ mã nguồn

Nếu muốn cài đặt và phát triển ứng dụng từ mã nguồn Python:

1.  **Tải mã nguồn về máy**:
    ```powershell
    git clone git@github.com:simenabba/win-translate.git
    cd win-translate
    ```

2.  **Cài đặt các thư viện cần thiết**:
    ```powershell
    pip install -r requirements.txt
    ```

3.  **Khởi chạy chương trình**:
    ```powershell
    python main.py
    ```

---

## 📦 Hướng dẫn đóng gói thành file chạy `.exe` độc lập

Để tạo ra file chạy `.exe` duy nhất có thể sử dụng di động hoặc gửi cho người khác chạy trực tiếp mà không cần cài đặt Python:

Chạy tập lệnh đóng gói tự động:
```powershell
python build_exe.py
```

*   Sau khi đóng gói thành công, tệp tin chạy sẽ nằm tại thư mục: `dist/win-translate.exe`.

---

## 📖 Hướng dẫn sử dụng phần mềm

1.  **Mở phần mềm**: Chạy file `main.py` hoặc file `win-translate.exe` đã đóng gói.
2.  **Chọn vùng quét**:
    *   Bấm nút **Chọn Vùng Dịch** trên bảng điều khiển.
    *   Màn hình sẽ mờ đi, nhấn giữ chuột trái và kéo vẽ một khung hình chữ nhật bao quanh khu vực có chữ trong game (ví dụ: khu vực hộp thoại nhân vật).
3.  **Điều chỉnh khung chữ dịch**:
    *   Bấm **Mở Khóa Khung Phụ Đề** để di chuyển khung dịch đến vị trí phù hợp, kéo góc dưới bên phải khung dịch để thay đổi chiều rộng/cao.
    *   Tinh chỉnh thanh trượt **Kích thước chữ** và **Độ đục nền phụ đề** (Opacity) trên bảng điều khiển để đọc rõ ràng nhất.
4.  **Bắt đầu dịch**:
    *   Chọn ngôn ngữ nguồn (ví dụ: `en-US` hoặc `ja`).
    *   Chọn dịch vụ dịch thuật mong muốn (mặc định là Google Translate).
    *   Bấm **Bắt Đầu Dịch** để khóa khung phụ đề, kích hoạt click xuyên thấu và chạy dịch thuật trực tiếp thời gian thực.
5.  **Dừng dịch**: Bấm **Dừng Dịch** để tắt quét màn hình và mở khóa lại khung phụ đề.

---

## 📄 Bản quyền và Cấp phép

Ứng dụng được phân phối và cấp phép theo các điều khoản của **Apache License 2.0**. Xem chi tiết tại tệp tin [LICENSE](file:///E:/Work/simenabba/win-translate/LICENSE).

Copyright © 2026 simenabba. All rights reserved.