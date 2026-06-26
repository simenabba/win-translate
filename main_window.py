import sys
from PyQt6.QtCore import Qt, pyqtSlot, QSettings
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QPushButton, QSlider, QPlainTextEdit, QGroupBox, QFormLayout, QCheckBox
)
from PyQt6.QtGui import QFont, QIcon, QColor

from ocr_engine import get_supported_languages
from selection_widget import SelectionWidget
from overlay_widget import OverlayWidget
from translator_thread import TranslatorThread
from audio_translator_thread import AudioTranslatorThread

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Win-Translate v1.0 - Trực Tiếp Game")
        self.resize(500, 600)
        import os
        basedir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(basedir, "app_icon.ico")
        self.setWindowIcon(QIcon(icon_path))
        
        # 1. Khởi tạo đối tượng lưu trữ cấu hình QSettings
        self.settings = QSettings("Simenabba", "WinTranslate")
        
        # Đọc lại tọa độ vùng chọn cũ (hoặc dùng mặc định nếu mở lần đầu)
        self.crop_x = self.settings.value("crop_x", 100, type=int)
        self.crop_y = self.settings.value("crop_y", 100, type=int)
        self.crop_w = self.settings.value("crop_w", 400, type=int)
        self.crop_h = self.settings.value("crop_h", 100, type=int)
        self.is_translating = False
        
        # Khởi tạo các Widgets phụ
        self.selection_widget = SelectionWidget()
        self.overlay_widget = OverlayWidget()
        
        # Khôi phục vị trí và kích thước cuối cùng của khung phụ đề Overlay
        ox = self.settings.value("overlay_x", 100, type=int)
        oy = self.settings.value("overlay_y", 100, type=int)
        ow = self.settings.value("overlay_w", 600, type=int)
        oh = self.settings.value("overlay_h", 150, type=int)
        self.overlay_widget.setGeometry(ox, oy, ow, oh)
        
        # Kết nối các tín hiệu của SelectionWidget
        self.selection_widget.selection_finished.connect(self.on_selection_finished)
        self.selection_widget.selection_cancelled.connect(self.on_selection_cancelled)
        
        # Kết nối tín hiệu hiển thị chữ của luồng dịch vào Overlay
        self.translator_thread = None
        self.audio_translator_thread = None
        self.stopping_threads = []
        
        # Khởi tạo Giao diện chính
        self.init_ui()
        self.apply_dark_theme()
        
        # Khôi phục các thiết lập UI từ phiên làm việc trước
        self.restore_ui_settings()
        
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
        
        # Thêm checkbox dịch âm thanh trực tiếp
        self.chk_audio_translate = QCheckBox("Bật dịch âm thanh hệ thống (STT)")
        self.chk_audio_translate.setChecked(False)
        self.chk_audio_translate.toggled.connect(self.on_audio_translate_toggled)
        
        # Thêm combo chọn ngôn ngữ nguồn âm thanh
        self.combo_audio_src_lang = QComboBox()
        self.combo_audio_src_lang.addItem("Tiếng Anh (en-US)", "en-US")
        self.combo_audio_src_lang.addItem("Tiếng Nhật (ja-JP)", "ja-JP")
        self.combo_audio_src_lang.addItem("Tiếng Trung (zh-CN)", "zh-CN")
        self.combo_audio_src_lang.addItem("Tiếng Hàn (ko-KR)", "ko-KR")
        self.combo_audio_src_lang.addItem("Tiếng Việt (vi-VN)", "vi-VN")
        self.combo_audio_src_lang.currentIndexChanged.connect(self.update_config_on_change)

        config_layout.addRow("Ngôn ngữ nguồn (OCR):", self.combo_src_lang)
        config_layout.addRow("Ngôn ngữ đích (Dịch):", self.combo_dest_lang)
        config_layout.addRow("Dịch vụ Dịch thuật:", self.combo_engine)
        config_layout.addRow("Tần suất quét màn hình:", interval_layout)
        config_layout.addRow("Dịch âm thanh (STT):", self.chk_audio_translate)
        config_layout.addRow("Nguồn âm thanh:", self.combo_audio_src_lang)
        
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
        
        # Nút nạp lại (Reload) ứng dụng nhanh
        self.btn_reload_app = QPushButton("Tải lại App")
        self.btn_reload_app.setObjectName("ReloadAppButton")
        self.btn_reload_app.clicked.connect(self.on_btn_reload_app_clicked)
        btn_layout.addWidget(self.btn_reload_app)
        
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
        QPushButton#ReloadAppButton {
            border-color: #7C7C8A;
            color: #A8A8B3;
        }
        QPushButton#ReloadAppButton:hover {
            background-color: rgba(255, 255, 255, 0.05);
            border-color: #00ADB5;
            color: #00ADB5;
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
        self.save_settings()

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
        
        # 1. Khởi tạo và khởi chạy luồng dịch ngầm
        self.translator_thread = TranslatorThread(
            self.crop_x, self.crop_y, self.crop_w, self.crop_h,
            src_lang, dest_lang, engine, interval
        )
        self.translator_thread.translation_ready.connect(self.overlay_widget.set_ocr_text)
        self.translator_thread.log_signal.connect(self.add_log)
        self.translator_thread.start()
        
        # 2. Khởi tạo và khởi chạy luồng dịch âm thanh ngầm nếu được bật
        if self.chk_audio_translate.isChecked():
            self.start_audio_translation()

    def start_audio_translation(self):
        """Khởi chạy luồng dịch âm thanh."""
        audio_src_lang = self.combo_audio_src_lang.currentData()
        dest_lang = self.combo_dest_lang.currentData()
        engine = self.combo_engine.currentData()
        
        self.audio_translator_thread = AudioTranslatorThread(
            audio_src_lang, dest_lang, engine
        )
        self.audio_translator_thread.translation_ready.connect(self.overlay_widget.set_audio_text)
        self.audio_translator_thread.log_signal.connect(self.add_log)
        self.audio_translator_thread.start()
        self.add_log(f"Bắt đầu lắng nghe và dịch âm thanh: {audio_src_lang} -> {dest_lang}")
            
    def stop_thread_async(self, thread):
        """Dừng luồng bất đồng bộ để tránh khóa GUI và quản lý bộ nhớ an toàn."""
        if not thread:
            return
            
        # 1. Ngắt kết nối các tín hiệu của luồng chính
        try:
            thread.translation_ready.disconnect()
        except Exception:
            pass
        try:
            thread.log_signal.disconnect()
        except Exception:
            pass
            
        # 2. Nếu là AudioTranslatorThread, ngắt kết nối cả worker phụ bên trong
        if hasattr(thread, 'worker') and thread.worker:
            try:
                thread.worker.translation_ready.disconnect()
            except Exception:
                pass
            try:
                thread.worker.log_signal.disconnect()
            except Exception:
                pass
                
            # Quản lý worker để tránh bị GC thu hồi sớm khi đang chạy ngầm
            worker = thread.worker
            if worker not in self.stopping_threads:
                self.stopping_threads.append(worker)
                worker.finished.connect(lambda w=worker: self.cleanup_thread(w))
                
        # 3. Kích hoạt lệnh dừng luồng
        thread.stop()
        
        # 4. Thêm luồng chính vào danh sách tracking để giữ tham chiếu an toàn
        if thread not in self.stopping_threads:
            self.stopping_threads.append(thread)
            thread.finished.connect(lambda t=thread: self.cleanup_thread(t))

    def cleanup_thread(self, thread):
        """Xóa luồng đã hoàn thành khỏi danh sách để thu hồi bộ nhớ sạch sẽ."""
        if thread in self.stopping_threads:
            self.stopping_threads.remove(thread)
            try:
                thread.deleteLater()
            except Exception:
                pass

    def stop_audio_translation(self):
        """Dừng luồng dịch âm thanh."""
        if self.audio_translator_thread:
            self.stop_thread_async(self.audio_translator_thread)
            self.audio_translator_thread = None
        self.overlay_widget.set_audio_text("")
        self.add_log("Đã dừng lắng nghe âm thanh.")

    def stop_translation(self):
        self.is_translating = False
        self.btn_toggle_translate.setText("Bắt Đầu Dịch")
        self.btn_toggle_translate.setStyleSheet("")
        
        if self.translator_thread:
            self.stop_thread_async(self.translator_thread)
            self.translator_thread = None
        self.overlay_widget.set_ocr_text("")
            
        self.stop_audio_translation()
            
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
            
        if self.audio_translator_thread:
            audio_src_lang = self.combo_audio_src_lang.currentData()
            dest_lang = self.combo_dest_lang.currentData()
            engine = self.combo_engine.currentData()
            self.audio_translator_thread.update_config(audio_src_lang, dest_lang, engine)

    def on_audio_translate_toggled(self, checked):
        """Xử lý sự kiện bật/tắt checkbox dịch âm thanh trực tiếp."""
        if self.is_translating:
            if checked:
                self.start_audio_translation()
            else:
                self.stop_audio_translation()

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

    def on_btn_reload_app_clicked(self):
        """Khởi động lại ứng dụng bằng cách mở tiến trình mới và đóng tiến trình cũ."""
        self.add_log("Đang khởi động lại ứng dụng...")
        self.save_settings()
        if self.translator_thread:
            self.stop_thread_async(self.translator_thread)
            self.translator_thread = None
        if self.audio_translator_thread:
            self.stop_thread_async(self.audio_translator_thread)
            self.audio_translator_thread = None
        self.selection_widget.close()
        self.overlay_widget.close()
        
        import subprocess
        import sys
        # Mở tiến trình Python mới chạy file main.py
        subprocess.Popen([sys.executable] + sys.argv)
        # Thoát ứng dụng hiện tại sạch sẽ
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def restore_ui_settings(self):
        """Khôi phục các giá trị của slider, combobox từ QSettings."""
        font_size = self.settings.value("font_size", 18, type=int)
        self.slider_font_size.setValue(font_size)
        self.lbl_font_size_val.setText(f"{font_size}px")
        
        bg_opacity = self.settings.value("bg_opacity", 70, type=int)
        self.slider_bg_opacity.setValue(bg_opacity)
        self.lbl_bg_opacity_val.setText(f"{bg_opacity}%")
        
        interval = self.settings.value("interval", 10, type=int)
        self.slider_interval.setValue(interval)
        self.lbl_interval_val.setText(f"{interval/10.0:.1f} giây")
        
        text_color_idx = self.settings.value("text_color_idx", 0, type=int)
        if text_color_idx < self.combo_text_color.count():
            self.combo_text_color.setCurrentIndex(text_color_idx)
            self.overlay_widget.set_text_color(self.combo_text_color.currentData())
            
        src_lang = self.settings.value("src_lang", "")
        if src_lang:
            idx = self.combo_src_lang.findData(src_lang)
            if idx != -1: self.combo_src_lang.setCurrentIndex(idx)
            
        dest_lang = self.settings.value("dest_lang", "vi")
        idx = self.combo_dest_lang.findData(dest_lang)
        if idx != -1: self.combo_dest_lang.setCurrentIndex(idx)
        
        engine = self.settings.value("engine", "Google")
        idx = self.combo_engine.findData(engine)
        if idx != -1: self.combo_engine.setCurrentIndex(idx)
        
        audio_translate = self.settings.value("audio_translate", False, type=bool)
        self.chk_audio_translate.setChecked(audio_translate)
        
        audio_src_lang = self.settings.value("audio_src_lang", "en-US")
        idx = self.combo_audio_src_lang.findData(audio_src_lang)
        if idx != -1: self.combo_audio_src_lang.setCurrentIndex(idx)

    def save_settings(self):
        """Lưu toàn bộ cấu hình hiện tại vào QSettings."""
        # Lưu vùng chọn dịch
        self.settings.setValue("crop_x", self.crop_x)
        self.settings.setValue("crop_y", self.crop_y)
        self.settings.setValue("crop_w", self.crop_w)
        self.settings.setValue("crop_h", self.crop_h)
        
        # Lưu vị trí và kích thước khung phụ đề Overlay
        self.settings.setValue("overlay_x", self.overlay_widget.x())
        self.settings.setValue("overlay_y", self.overlay_widget.y())
        self.settings.setValue("overlay_w", self.overlay_widget.width())
        self.settings.setValue("overlay_h", self.overlay_widget.height())
        
        # Lưu các cấu hình UI khác
        self.settings.setValue("font_size", self.slider_font_size.value())
        self.settings.setValue("bg_opacity", self.slider_bg_opacity.value())
        self.settings.setValue("interval", self.slider_interval.value())
        self.settings.setValue("text_color_idx", self.combo_text_color.currentIndex())
        self.settings.setValue("src_lang", self.combo_src_lang.currentData())
        self.settings.setValue("dest_lang", self.combo_dest_lang.currentData())
        self.settings.setValue("engine", self.combo_engine.currentData())
        self.settings.setValue("audio_translate", self.chk_audio_translate.isChecked())
        self.settings.setValue("audio_src_lang", self.combo_audio_src_lang.currentData())

    def closeEvent(self, event):
        """Hành vi dọn dẹp khi đóng cửa sổ chính."""
        self.save_settings()
        if self.translator_thread:
            self.stop_thread_async(self.translator_thread)
            self.translator_thread = None
        if self.audio_translator_thread:
            self.stop_thread_async(self.audio_translator_thread)
            self.audio_translator_thread = None
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
