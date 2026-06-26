import sys
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QSlider, QPlainTextEdit, QGroupBox, QFormLayout
)
from PyQt6.QtGui import QFont, QIcon, QColor

from ocr_engine import get_supported_languages
from selection_widget import SelectionWidget
from overlay_widget import OverlayWidget
from translator_thread import TranslatorThread

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Win-Translate v1.0 - Trực Tiếp Game")
        self.resize(500, 600)
        import os
        basedir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(basedir, "app_icon.ico")
        self.setWindowIcon(QIcon(icon_path))
        
        # Lưu trữ trạng thái tọa độ vùng chọn (mặc định chọn vùng trung tâm nếu chưa vẽ)
        self.crop_x = 100
        self.crop_y = 100
        self.crop_w = 400
        self.crop_h = 100
        self.is_translating = False
        
        # Khởi tạo các Widgets phụ
        self.selection_widget = SelectionWidget()
        self.overlay_widget = OverlayWidget()
        
        # Kết nối các tín hiệu của SelectionWidget
        self.selection_widget.selection_finished.connect(self.on_selection_finished)
        self.selection_widget.selection_cancelled.connect(self.on_selection_cancelled)
        
        # Kết nối tín hiệu hiển thị chữ của luồng dịch vào Overlay
        self.translator_thread = None
        
        # Khởi tạo Giao diện chính
        self.init_ui()
        self.apply_dark_theme()
        
        # Đồng bộ trạng thái overlay ban đầu
        self.overlay_widget.set_font_size(self.slider_font_size.value())
        self.overlay_widget.set_bg_opacity(int(self.slider_bg_opacity.value() * 2.55))
        self.overlay_widget.set_lock(False)
        self.overlay_widget.show()
        
        self.add_log("Phần mềm đã sẵn sàng. Hãy bấm 'Chọn vùng dịch' để khoanh vùng chữ cần dịch.")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 1. Tiêu đề
        title_label = QLabel("WIN-TRANSLATE")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        main_layout.addWidget(title_label)
        
        # 2. Nhóm cấu hình dịch thuật
        config_group = QGroupBox("Cấu hình Dịch thuật")
        config_layout = QFormLayout(config_group)
        config_layout.setSpacing(10)
        
        self.combo_src_lang = QComboBox()
        # Nạp danh sách các ngôn ngữ Windows OCR hỗ trợ
        supported_langs = get_supported_languages()
        if supported_langs:
            for lang in supported_langs:
                self.combo_src_lang.addItem(lang, lang)
            # Chọn en-US hoặc ja làm mặc định nếu có
            default_idx = self.combo_src_lang.findData("en-US")
            if default_idx == -1:
                default_idx = self.combo_src_lang.findData("ja")
            if default_idx != -1:
                self.combo_src_lang.setCurrentIndex(default_idx)
        else:
            self.combo_src_lang.addItem("Không tìm thấy OCR Pack!", "none")
            self.combo_src_lang.setEnabled(False)
            
        self.combo_dest_lang = QComboBox()
        self.combo_dest_lang.addItem("Tiếng Việt (vi)", "vi")
        self.combo_dest_lang.addItem("Tiếng Anh (en)", "en")
        
        self.combo_engine = QComboBox()
        self.combo_engine.addItem("Google Translate (Free)", "Google")
        self.combo_engine.addItem("MyMemory Translate (Free)", "MyMemory")
        
        # Thanh trượt giãn cách dịch
        self.slider_interval = QSlider(Qt.Orientation.Horizontal)
        self.slider_interval.setMinimum(5)   # 0.5 giây
        self.slider_interval.setMaximum(30)  # 3.0 giây
        self.slider_interval.setValue(10)    # 1.0 giây mặc định
        self.lbl_interval_val = QLabel("1.0 giây")
        self.slider_interval.valueChanged.connect(self.on_interval_changed)
        
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(self.slider_interval)
        interval_layout.addWidget(self.lbl_interval_val)
        
        config_layout.addRow("Ngôn ngữ nguồn (OCR):", self.combo_src_lang)
        config_layout.addRow("Ngôn ngữ đích (Dịch):", self.combo_dest_lang)
        config_layout.addRow("Dịch vụ Dịch thuật:", self.combo_engine)
        config_layout.addRow("Tần suất quét màn hình:", interval_layout)
        
        main_layout.addWidget(config_group)
        
        # 3. Nhóm cấu hình phụ đề hiển thị (Overlay)
        style_group = QGroupBox("Cấu hình Phụ đề hiển thị")
        style_layout = QFormLayout(style_group)
        style_layout.setSpacing(10)
        
        # Kích thước font
        self.slider_font_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_font_size.setMinimum(12)
        self.slider_font_size.setMaximum(36)
        self.slider_font_size.setValue(18)
        self.lbl_font_size_val = QLabel("18px")
        self.slider_font_size.valueChanged.connect(self.on_font_size_changed)
        
        font_layout = QHBoxLayout()
        font_layout.addWidget(self.slider_font_size)
        font_layout.addWidget(self.lbl_font_size_val)
        
        # Độ trong suốt của nền hộp dịch
        self.slider_bg_opacity = QSlider(Qt.Orientation.Horizontal)
        self.slider_bg_opacity.setMinimum(0)
        self.slider_bg_opacity.setMaximum(100)
        self.slider_bg_opacity.setValue(70) # 70% mờ đục
        self.lbl_bg_opacity_val = QLabel("70%")
        self.slider_bg_opacity.valueChanged.connect(self.on_bg_opacity_changed)
        
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(self.slider_bg_opacity)
        opacity_layout.addWidget(self.lbl_bg_opacity_val)
        
        # Màu sắc chữ
        self.combo_text_color = QComboBox()
        self.combo_text_color.addItem("Trắng (Mặc định)", QColor(255, 255, 255))
        self.combo_text_color.addItem("Vàng", QColor(255, 255, 0))
        self.combo_text_color.addItem("Xanh ngọc (Cyan)", QColor(0, 255, 255))
        self.combo_text_color.addItem("Xanh lá", QColor(0, 255, 0))
        self.combo_text_color.addItem("Đỏ nhạt", QColor(255, 100, 100))
        self.combo_text_color.addItem("Cam", QColor(255, 165, 0))
        self.combo_text_color.currentIndexChanged.connect(self.on_text_color_changed)
        
        style_layout.addRow("Kích thước chữ:", font_layout)
        style_layout.addRow("Độ đục nền phụ đề:", opacity_layout)
        style_layout.addRow("Màu sắc chữ phụ đề:", self.combo_text_color)
        
        main_layout.addWidget(style_group)
        
        # 4. Các nút điều khiển hành động
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_select_area = QPushButton("Chọn Vùng Dịch")
        self.btn_select_area.setObjectName("SelectAreaButton")
        self.btn_select_area.clicked.connect(self.on_btn_select_area_clicked)
        btn_layout.addWidget(self.btn_select_area)
        
        self.btn_toggle_translate = QPushButton("Bắt Đầu Dịch")
        self.btn_toggle_translate.setObjectName("StartTranslateButton")
        self.btn_toggle_translate.clicked.connect(self.on_btn_toggle_translate_clicked)
        btn_layout.addWidget(self.btn_toggle_translate)
        
        main_layout.addLayout(btn_layout)
        
        # Hộp thoại check khóa/mở khóa overlay thủ công
        self.btn_lock_overlay = QPushButton("Mở Khóa Khung Phụ Đề")
        self.btn_lock_overlay.setObjectName("LockOverlayButton")
        self.btn_lock_overlay.setCheckable(True)
        self.btn_lock_overlay.clicked.connect(self.on_btn_lock_overlay_clicked)
        main_layout.addWidget(self.btn_lock_overlay)
        
        # 5. Nhật ký log hệ thống
        log_group = QGroupBox("Nhật ký hệ thống")
        log_layout = QVBoxLayout(log_group)
        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setMaximumHeight(150)
        log_layout.addWidget(self.log_console)
        
        main_layout.addWidget(log_group)
        
        # Nhãn hiển thị tọa độ hiện tại
        self.lbl_coordinates = QLabel(f"Vùng chụp hiện tại: X={self.crop_x}, Y={self.crop_y}, W={self.crop_w}, H={self.crop_h}")
        self.lbl_coordinates.setObjectName("CoordLabel")
        self.lbl_coordinates.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.lbl_coordinates)

    def apply_dark_theme(self):
        """Thiết kế giao diện tối hiện đại, cao cấp với các chi tiết màu neon xanh."""
        qss = """
        QMainWindow {
            background-color: #121214;
        }
        QWidget {
            color: #E1E1E6;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
        }
        QLabel#TitleLabel {
            color: #00ADB5;
            letter-spacing: 2px;
            margin-bottom: 5px;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #29292E;
            border-radius: 6px;
            margin-top: 15px;
            padding-top: 15px;
            color: #00ADB5;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 5px;
        }
        QComboBox {
            background-color: #202024;
            border: 1px solid #29292E;
            border-radius: 4px;
            padding: 5px 10px;
            min-width: 150px;
            color: #E1E1E6;
        }
        QComboBox::drop-down {
            border: 0px;
        }
        QComboBox QAbstractItemView {
            background-color: #202024;
            border: 1px solid #29292E;
            selection-background-color: #00ADB5;
            selection-color: #121214;
            color: #E1E1E6;
        }
        QSlider::groove:horizontal {
            border: 1px solid #29292E;
            height: 6px;
            background: #202024;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #00ADB5;
            border: 1px solid #00ADB5;
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }
        QPushButton {
            background-color: #202024;
            border: 1px solid #29292E;
            border-radius: 4px;
            padding: 8px 15px;
            font-weight: bold;
            color: #E1E1E6;
            min-height: 20px;
        }
        QPushButton:hover {
            background-color: #29292E;
            border-color: #00ADB5;
        }
        QPushButton:pressed {
            background-color: #121214;
        }
        QPushButton#SelectAreaButton {
            border-color: #00ADB5;
            color: #00ADB5;
        }
        QPushButton#SelectAreaButton:hover {
            background-color: rgba(0, 173, 181, 0.1);
        }
        QPushButton#StartTranslateButton {
            background-color: #00ADB5;
            color: #121214;
            border: none;
        }
        QPushButton#StartTranslateButton:hover {
            background-color: #00FFF5;
        }
        QPushButton#StartTranslateButton:checked {
            background-color: #E63946;
            color: white;
        }
        QPushButton#LockOverlayButton {
            background-color: #202024;
            border: 1px dashed #29292E;
            color: #A8A8B3;
        }
        QPushButton#LockOverlayButton:checked {
            background-color: rgba(230, 57, 70, 0.1);
            border: 1px solid #E63946;
            color: #E63946;
        }
        QPlainTextEdit {
            background-color: #09090A;
            border: 1px solid #202024;
            border-radius: 4px;
            font-family: 'Consolas', 'Courier New', monospace;
            color: #A8A8B3;
            font-size: 11px;
        }
        QLabel#CoordLabel {
            font-size: 11px;
            color: #7C7C8A;
        }
        """
        self.setStyleSheet(qss)

    def add_log(self, message):
        """Thêm một dòng log kèm mốc thời gian."""
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_console.appendPlainText(f"[{time_str}] {message}")

    # Xử lý các sự kiện thay đổi thanh trượt
    def on_interval_changed(self, value):
        val_sec = value / 10.0
        self.lbl_interval_val.setText(f"{val_sec:.1f} giây")
        if self.is_translating and self.translator_thread:
            self.update_thread_config()

    def on_font_size_changed(self, value):
        self.lbl_font_size_val.setText(f"{value}px")
        self.overlay_widget.set_font_size(value)

    def on_bg_opacity_changed(self, value):
        self.lbl_bg_opacity_val.setText(f"{value}%")
        # Chuyển đổi từ % (0-100) sang kênh alpha màu (0-255)
        self.overlay_widget.set_bg_opacity(int(value * 2.55))

    def on_text_color_changed(self):
        color = self.combo_text_color.currentData()
        self.overlay_widget.set_text_color(color)
        self.add_log("Đã đổi màu chữ hiển thị phụ đề.")

    # Xử lý nút Chọn vùng màn hình
    def on_btn_select_area_clicked(self):
        self.add_log("Đang mở công cụ chọn vùng. Hãy kéo chuột vẽ ô chọn hoặc nhấn ESC để hủy.")
        # Nếu đang dịch thì tắt đi
        if self.is_translating:
            self.stop_translation()
            
        self.selection_widget.show_selection()

    @pyqtSlot(int, int, int, int)
    def on_selection_finished(self, x, y, w, h):
        self.crop_x = x
        self.crop_y = y
        self.crop_w = w
        self.crop_h = h
        self.lbl_coordinates.setText(f"Vùng chụp hiện tại: X={x}, Y={y}, W={w}, H={h}")
        self.add_log(f"Đã cập nhật vùng chụp: X={x}, Y={y}, W={w}, H={h}")
        
        # Chỉ hiển thị khung overlay, không di chuyển/snap tọa độ
        # Giúp giữ vị trí cố định do người dùng tự kéo chỉnh
        self.overlay_widget.show()
        
        if self.translator_thread:
            self.translator_thread.update_region(x, y, w, h)

    @pyqtSlot()
    def on_selection_cancelled(self):
        self.add_log("Đã hủy chọn vùng màn hình.")

    # Xử lý nút Bật/Tắt dịch
    def on_btn_toggle_translate_clicked(self):
        if not self.is_translating:
            self.start_translation()
        else:
            self.stop_translation()

    def start_translation(self):
        src_lang = self.combo_src_lang.currentData()
        dest_lang = self.combo_dest_lang.currentData()
        engine = self.combo_engine.currentData()
        interval = self.slider_interval.value() / 10.0
        
        if src_lang == "none":
            self.add_log("LỖI: Chưa cài đặt ngôn ngữ nguồn.")
            return
            
        self.is_translating = True
        self.btn_toggle_translate.setText("Dừng Dịch")
        self.btn_toggle_translate.setStyleSheet("background-color: #E63946; color: white;")
        
        # Khóa overlay hiển thị và kích hoạt click-through để click xuyên qua game
        self.overlay_widget.set_lock(True)
        # Đồng bộ nút lock overlay
        self.btn_lock_overlay.setChecked(False)
        self.btn_lock_overlay.setText("Mở Khóa Khung Phụ Đề")
        
        # Khởi tạo và khởi chạy luồng dịch ngầm
        self.translator_thread = TranslatorThread(
            self.crop_x, self.crop_y, self.crop_w, self.crop_h,
            src_lang, dest_lang, engine, interval
        )
        self.translator_thread.translation_ready.connect(self.overlay_widget.set_text)
        self.translator_thread.log_signal.connect(self.add_log)
        self.translator_thread.start()
        
        self.add_log(f"Bắt đầu dịch trực tiếp game: {src_lang} -> {dest_lang}")

    def stop_translation(self):
        self.is_translating = False
        self.btn_toggle_translate.setText("Bắt Đầu Dịch")
        self.btn_toggle_translate.setStyleSheet("")
        
        if self.translator_thread:
            self.translator_thread.stop()
            self.translator_thread = None
            
        # Mở khóa overlay để người dùng có thể tương tác (di chuyển, thay đổi cỡ) nếu muốn
        self.overlay_widget.set_lock(False)
        self.btn_lock_overlay.setChecked(True)
        self.btn_lock_overlay.setText("Khóa Khung Phụ Đề")
        self.add_log("Đã dừng dịch trực tiếp.")

    def update_thread_config(self):
        if self.translator_thread:
            src_lang = self.combo_src_lang.currentData()
            dest_lang = self.combo_dest_lang.currentData()
            engine = self.combo_engine.currentData()
            interval = self.slider_interval.value() / 10.0
            self.translator_thread.update_config(src_lang, dest_lang, engine, interval)

    # Khóa / Mở khóa khung dịch thủ công bằng nút bấm
    def on_btn_lock_overlay_clicked(self, checked):
        if checked:
            self.overlay_widget.set_lock(False)
            self.btn_lock_overlay.setText("Khóa Khung Phụ Đề")
            self.add_log("Khung dịch ĐÃ MỞ KHÓA. Bạn có thể kéo và kéo góc phải để chỉnh kích cỡ phụ đề.")
        else:
            self.overlay_widget.set_lock(True)
            self.btn_lock_overlay.setText("Mở Khóa Khung Phụ Đề")
            self.add_log("Khung dịch ĐÃ KHÓA và Click-through được bật.")

    # Thay đổi lựa chọn ngôn ngữ
    def update_config_on_change(self):
        if self.is_translating:
            self.update_thread_config()

    def closeEvent(self, event):
        """Hành vi dọn dẹp khi đóng cửa sổ chính."""
        if self.translator_thread:
            self.translator_thread.stop()
        self.selection_widget.close()
        self.overlay_widget.close()
        event.accept()

# Điểm chạy test độc lập
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
