import sys
import traceback
import os
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from main_window import MainWindow

# Đường dẫn tệp tin log ghi lỗi
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crash.log")

class WriteLogger:
    """Lớp ghi đè luồng xuất dữ liệu (stdout/stderr) ra tệp tin log."""
    def __init__(self, filepath, stream):
        self.filepath = filepath
        self.stream = stream

    def write(self, data):
        # Xuất ra luồng chuẩn ban đầu (console nếu có)
        if self.stream:
            try:
                self.stream.write(data)
            except:
                try:
                    # Ghi đè kí tự lỗi bằng dấu ? để tránh sập ứng dụng
                    self.stream.write(data.encode(getattr(self.stream, 'encoding', 'utf-8') or 'utf-8', errors='replace').decode(getattr(self.stream, 'encoding', 'utf-8') or 'utf-8'))
                except:
                    pass
        # Ghi vào file log nếu có dữ liệu thực sự
        if data.strip():
            try:
                with open(self.filepath, "a", encoding="utf-8") as f:
                    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{time_str}] {data}\n")
            except:
                pass

    def flush(self):
        if self.stream:
            self.stream.flush()

def log_exception(exc_type, exc_value, exc_traceback):
    """Bắt và ghi nhận các lỗi chưa xử lý (unhandled exceptions) làm sập app."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n=================== HỆ THỐNG SẬP VÀO LÚC {time_str} ===================\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    except:
        pass
        
    # Gọi lại trình hiển thị lỗi gốc của hệ thống
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def main():
    # 1. Kích hoạt hệ thống ghi log lỗi
    sys.excepthook = log_exception
    sys.stdout = WriteLogger(LOG_FILE, sys.stdout)
    sys.stderr = WriteLogger(LOG_FILE, sys.stderr)

    print("Khởi động ứng dụng Win-Translate...")

    # 2. Khởi tạo ứng dụng Qt
    app = QApplication(sys.argv)
    
    # 3. Khởi tạo và hiển thị cửa sổ điều khiển chính
    window = MainWindow()
    window.show()
    
    # 4. Bắt đầu vòng lặp sự kiện của PyQt
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
