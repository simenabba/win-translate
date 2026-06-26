from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtGui import QPainter, QColor, QPen, QGuiApplication

class SelectionWidget(QWidget):
    # Signal phát ra khi chọn xong vùng: (x, y, w, h)
    selection_finished = pyqtSignal(int, int, int, int)
    # Signal phát ra khi người dùng hủy chọn (ví dụ: nhấn ESC)
    selection_cancelled = pyqtSignal()

    def __init__(self):
        super().__init__()
        # Thiết lập cửa sổ không viền, luôn hiển thị trên cùng, và là Tool Window (không tạo tab dưới Taskbar)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Lấy kích thước toàn bộ màn hình chính
        screen = QGuiApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False

        # Đặt con trỏ chuột dạng chữ thập
        self.setCursor(Qt.CursorShape.CrossCursor)

    def show_selection(self):
        """Khởi động lại vùng chọn và hiển thị cửa sổ."""
        # Cập nhật kích thước màn hình phòng trường hợp độ phân giải thay đổi
        screen = QGuiApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        self.start_pos = QPoint()
        self.end_pos = QPoint()
        self.is_selecting = False
        self.showFullScreen()
        self.activateWindow()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Vẽ một lớp màn mờ màu đen xám phủ toàn màn hình
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))
        
        if self.is_selecting:
            # Tính toán hình chữ nhật hiện tại đang vẽ
            rect = QRect(self.start_pos, self.end_pos)
            
            # Cắt rỗng (trong suốt hoàn toàn) vùng chọn đang kéo
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)
            
            # Vẽ đường viền màu đỏ xung quanh vùng chọn
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor(255, 60, 60, 255), 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = event.position().toPoint()
            self.end_pos = self.start_pos
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_pos = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.end_pos = event.position().toPoint()
            
            # Tính toán tọa độ chuẩn (không bị số âm khi kéo ngược hướng)
            x = min(self.start_pos.x(), self.end_pos.x())
            y = min(self.start_pos.y(), self.end_pos.y())
            w = abs(self.start_pos.x() - self.end_pos.x())
            h = abs(self.start_pos.y() - self.end_pos.y())
            
            self.close()
            
            # Chỉ phát tín hiệu nếu diện tích chọn đủ lớn (>15 pixel mỗi chiều)
            if w > 15 and h > 15:
                self.selection_finished.emit(x, y, w, h)
            else:
                self.selection_cancelled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.selection_cancelled.emit()

# Test nhanh độc lập
if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    widget = SelectionWidget()
    
    widget.selection_finished.connect(lambda x, y, w, h: print(f"Đã chọn vùng: X={x}, Y={y}, W={w}, H={h}"))
    widget.selection_cancelled.connect(lambda: print("Đã hủy chọn vùng"))
    
    widget.show_selection()
    sys.exit(app.exec())
