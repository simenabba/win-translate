import sys
import ctypes
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtWidgets import QWidget, QApplication, QLabel, QVBoxLayout
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush

# Các hằng số Windows API để làm xuyên thấu chuột (click-through)
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000

# Cấu hình an toàn Win32 API hỗ trợ cả Windows 32-bit và 64-bit (Tránh sập app do tràn số con trỏ)
user32 = ctypes.windll.user32
IS_64BIT = sys.maxsize > 2**32

if IS_64BIT:
    GetWindowLong = user32.GetWindowLongPtrW
    SetWindowLong = user32.SetWindowLongPtrW
    GetWindowLong.restype = ctypes.c_ssize_t
    GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
    SetWindowLong.restype = ctypes.c_ssize_t
    SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
else:
    GetWindowLong = user32.GetWindowLongW
    SetWindowLong = user32.SetWindowLongW
    GetWindowLong.restype = ctypes.c_long
    GetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int]
    SetWindowLong.restype = ctypes.c_long
    SetWindowLong.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]


class OverlayWidget(QWidget):
    def __init__(self):
        super().__init__()
        # Thiết lập cửa sổ không viền, luôn nổi trên cùng, và là Tool Window
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        # Nền trong suốt
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Khởi tạo mặc định
        self.is_locked = False
        self.is_resizing = False
        self.drag_position = QPoint()
        self.ocr_text = ""
        self.audio_text = ""
        self.audio_text_color = QColor(255, 223, 0) # Màu vàng neon sáng
        self.bg_opacity = 180  # Mặc định nền hộp thoại mờ (0 - 255)
        self.text_color = QColor(255, 255, 255) # Chữ trắng
        self.font_size = 18
        
        # Thiết lập kích thước mặc định và vị trí
        self.setGeometry(100, 100, 600, 150)
        self.setMinimumSize(150, 50)
        
        # Đặt font chữ
        self.overlay_font = QFont("Arial", self.font_size, QFont.Weight.Bold)

    def set_ocr_text(self, text):
        """Cập nhật văn bản dịch từ OCR."""
        self.ocr_text = text
        self.update()

    def set_text(self, text):
        """Hàm cũ làm alias cho set_ocr_text để đảm bảo tính tương thích."""
        self.set_ocr_text(text)

    def set_audio_text(self, text):
        """Cập nhật văn bản dịch từ âm thanh trực tiếp."""
        self.audio_text = text
        self.update()

    def set_font_size(self, size):
        """Thay đổi kích thước font."""
        self.font_size = size
        self.overlay_font = QFont("Arial", self.font_size, QFont.Weight.Bold)
        self.update()

    def set_bg_opacity(self, opacity):
        """Thay đổi độ mờ của nền (0 đến 255)."""
        self.bg_opacity = opacity
        self.update()

    def set_text_color(self, color):
        """Thay đổi màu chữ dịch chính."""
        self.text_color = color
        self.update()

    def set_lock(self, lock=True):
        """Khóa/Mở khóa khung dịch.
        - Khóa: Không thể di chuyển, click xuyên thấu qua game, nền trong suốt hoàn toàn hoặc theo độ trong suốt cấu hình.
        - Mở khóa: Có thể kéo di chuyển, thay đổi kích thước, nền đục hơn để nhận biết.
        """
        self.is_locked = lock
        hwnd = int(self.winId())
        
        # Lấy style hiện tại bằng hàm an toàn 64-bit
        try:
            style = GetWindowLong(hwnd, GWL_EXSTYLE)
            
            if lock:
                # Thêm cờ xuyên thấu (click-through)
                style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
                SetWindowLong(hwnd, GWL_EXSTYLE, style)
                self.setCursor(Qt.CursorShape.ArrowCursor)
            else:
                # Bỏ cờ xuyên thấu để có thể tương tác chuột
                style &= ~WS_EX_TRANSPARENT
                SetWindowLong(hwnd, GWL_EXSTYLE, style)
                self.setCursor(Qt.CursorShape.SizeAllCursor)
        except Exception as e:
            print(f"Lỗi cấu hình click-through Windows API: {e}", file=sys.stderr)
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Vẽ nền
        if not self.is_locked:
            # Chế độ Edit: Vẽ nền xám mờ và viền đứt nét để người dùng dễ nhìn thấy khung để kéo
            painter.fillRect(self.rect(), QColor(40, 40, 40, 160))
            
            # Vẽ viền màu xanh dương nhạt để chỉ thị chế độ Edit
            pen = QPen(QColor(0, 150, 255, 200), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
            
            # Vẽ nút kéo chỉnh kích thước ở góc dưới bên phải
            painter.setBrush(QBrush(QColor(0, 150, 255, 200)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(self.width() - 15, self.height() - 15, 15, 15)
        else:
            # Chế độ Dịch: Vẽ nền mờ theo cấu hình (ví dụ nền đen mờ giúp đọc chữ dễ hơn)
            if self.bg_opacity > 0 and (self.ocr_text or self.audio_text):
                painter.fillRect(self.rect(), QColor(0, 0, 0, self.bg_opacity))
                
        # 2. Vẽ chữ dịch
        painter.setFont(self.overlay_font)
        rect_margin = self.rect().adjusted(15, 10, -15, -10)
        
        has_audio = bool(self.audio_text.strip())
        has_ocr = bool(self.ocr_text.strip())
        
        def draw_text_with_shadow(rect, text, color, alignment=Qt.AlignmentFlag.AlignCenter):
            # Vẽ bóng đổ cho chữ để đọc rõ hơn trên mọi nền game (kể cả khi tắt nền)
            if self.bg_opacity < 100:
                painter.setPen(QColor(0, 0, 0, 220))
                # Vẽ dịch bóng xuống 2 pixel sang phải 2 pixel
                shadow_rect = rect.adjusted(2, 2, 2, 2)
                painter.drawText(
                    shadow_rect, 
                    alignment | Qt.TextFlag.TextWordWrap, 
                    text
                )
                
            # Vẽ chữ chính
            painter.setPen(color)
            painter.drawText(
                rect, 
                alignment | Qt.TextFlag.TextWordWrap, 
                text
            )

        if not self.is_locked:
            # Ở chế độ Edit, hiển thị gợi ý
            demo_text = "[Kéo thả để di chuyển hoặc kéo góc phải để chỉnh kích cỡ phụ đề]"
            draw_text_with_shadow(rect_margin, demo_text, QColor(0, 150, 255))
        else:
            # Chia đôi khung dịch cố định (50% trên cho dịch âm thanh, 50% dưới cho OCR)
            height_half = rect_margin.height() // 2
            
            audio_rect = QRect(rect_margin.left(), rect_margin.top(), rect_margin.width(), height_half - 4)
            ocr_rect = QRect(rect_margin.left(), rect_margin.top() + height_half + 4, rect_margin.width(), height_half - 4)
            
            # Luôn vẽ một đường phân chia mờ ở giữa khi có một trong hai văn bản để phân tách rõ ranh giới hai nửa
            if has_audio or has_ocr:
                painter.setPen(QColor(100, 100, 100, 80))
                painter.drawLine(rect_margin.left(), rect_margin.top() + height_half, 
                                 rect_margin.right(), rect_margin.top() + height_half)
            
            # Vẽ phần dịch âm thanh nếu có (luôn ở nửa trên, căn lề trái và căn giữa dọc)
            if has_audio:
                draw_text_with_shadow(
                    audio_rect, 
                    f"🔊 {self.audio_text}", 
                    self.audio_text_color,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
            
            # Vẽ phần dịch OCR màn hình nếu có (luôn ở nửa dưới, căn lề trái và căn giữa dọc)
            if has_ocr:
                draw_text_with_shadow(
                    ocr_rect, 
                    self.ocr_text, 
                    self.text_color,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )

    # Các sự kiện di chuyển và thay đổi kích thước bằng chuột ở chế độ Edit
    def mousePressEvent(self, event):
        if self.is_locked:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            # Kiểm tra nếu click vào góc dưới phải (15x15 pixel) để thay đổi kích thước
            if pos.x() > self.width() - 20 and pos.y() > self.height() - 20:
                self.is_resizing = True
            else:
                self.is_resizing = False
                # Ghi nhớ vị trí click để di chuyển cửa sổ
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_locked:
            return
        if event.buttons() == Qt.MouseButton.LeftButton:
            if self.is_resizing:
                global_pos = event.globalPosition().toPoint()
                # Tính kích thước mới
                new_width = max(150, global_pos.x() - self.x())
                new_height = max(50, global_pos.y() - self.y())
                self.resize(new_width, new_height)
            else:
                self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.is_locked:
            return
        self.is_resizing = False
        event.accept()

# Chạy thử độc lập
if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = OverlayWidget()
    overlay.set_text("Đây là dòng chữ phụ đề được dịch thử nghiệm đè lên game. Bạn có thể kéo di chuyển khung này ở chế độ mở khóa.")
    overlay.show()
    
    # Hẹn giờ khóa sau 5 giây để test click-through
    from PyQt6.QtCore import QTimer
    print("Mở khóa. Di chuyển cửa sổ tùy ý...")
    
    def lock_test():
        print("Đang KHÓA khung dịch! Hãy thử rê chuột và click xuyên qua nó.")
        overlay.set_lock(True)
        
    QTimer.singleShot(5000, lock_test)
    sys.exit(app.exec())
