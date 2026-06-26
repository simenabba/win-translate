import time
import mss
from PIL import Image, ImageEnhance, ImageOps
from PyQt6.QtCore import QThread, pyqtSignal
from ocr_engine import WindowsOcrEngine
from deep_translator import GoogleTranslator, MyMemoryTranslator

def map_lang_code(win_tag):
    """Ánh xạ mã ngôn ngữ Windows OCR sang mã ngôn ngữ deep-translator."""
    win_tag = win_tag.lower()
    if win_tag.startswith("en"):
        return "en"
    elif win_tag.startswith("ja"):
        return "ja"
    elif win_tag.startswith("vi"):
        return "vi"
    elif win_tag.startswith("zh"):
        # Tiếng Trung giản thể hoặc phồn thể
        if "hans" in win_tag or "cn" in win_tag:
            return "zh-CN"
        else:
            return "zh-TW"
    elif win_tag.startswith("ko"):
        return "ko"
    elif win_tag.startswith("ru"):
        return "ru"
    elif win_tag.startswith("fr"):
        return "fr"
    elif win_tag.startswith("de"):
        return "de"
    # Mặc định lấy 2 ký tự đầu
    return win_tag[:2]

def map_mymemory_lang_code(lang_code):
    """Ánh xạ mã ngôn ngữ sang mã mà MyMemory hỗ trợ để tránh lỗi không hỗ trợ en/vi."""
    lang_code = lang_code.lower()
    mapping = {
        "en": "en-US",
        "vi": "vi-VN",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "zh-cn": "zh-CN",
        "zh-tw": "zh-TW",
        "fr": "fr-FR",
        "de": "de-DE",
        "ru": "ru-RU",
    }
    if lang_code in mapping:
        return mapping[lang_code]
    for key, val in mapping.items():
        if lang_code.startswith(key):
            return val
    return lang_code


class TranslatorThread(QThread):
    # Phát đi dòng chữ đã dịch về cho UI
    translation_ready = pyqtSignal(str)
    # Phát đi nhật ký logs hiển thị lên Main Window
    log_signal = pyqtSignal(str)
    
    def __init__(self, x, y, w, h, src_lang="en-US", dest_lang="vi", engine_type="Google", interval=1.0):
        super().__init__()
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.src_lang = src_lang
        self.dest_lang = dest_lang
        self.engine_type = engine_type
        self.interval = interval
        
        self.running = False
        self.ocr_engine = None
        self.last_ocr_text = ""
        self.translation_cache = {} # Dict lưu cache: {ocr_text: translated_text}
        
    def update_region(self, x, y, w, h):
        """Cập nhật tọa độ vùng chụp."""
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.log_signal.emit(f"Cập nhật vùng dịch: X={x}, Y={y}, W={w}, H={h}")

    def update_config(self, src_lang, dest_lang, engine_type, interval):
        """Cập nhật cấu hình dịch."""
        self.dest_lang = dest_lang
        self.engine_type = engine_type
        self.interval = interval
        
        # Nếu đổi ngôn ngữ nguồn, cần tạo lại OcrEngine
        if self.src_lang != src_lang:
            self.src_lang = src_lang
            self.ocr_engine = None # Sẽ khởi tạo lại trong luồng run()
            
        self.log_signal.emit(
            f"Cập nhật cấu hình: Nguồn={src_lang}, Đích={dest_lang}, Engine={engine_type}, Giãn cách={interval}s"
        )
        # Xóa bộ nhớ đệm vì ngôn ngữ đích có thể thay đổi
        self.translation_cache.clear()

    def translate_text(self, text):
        """Thực hiện dịch văn bản bằng engine đã chọn với cơ chế fallback."""
        if not text.strip():
            return ""
            
        # Kiểm tra bộ nhớ cache trước
        cache_key = (self.src_lang, self.dest_lang, self.engine_type, text)
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
            
        src_code = map_lang_code(self.src_lang)
        dest_code = map_lang_code(self.dest_lang)
        
        translated = ""
        # 1. Thử dịch bằng Engine được chỉ định
        try:
            if self.engine_type == "Google":
                translator = GoogleTranslator(source=src_code, target=dest_code)
                translated = translator.translate(text)
            elif self.engine_type == "MyMemory":
                mym_src = map_mymemory_lang_code(src_code)
                mym_dest = map_mymemory_lang_code(dest_code)
                translator = MyMemoryTranslator(source=mym_src, target=mym_dest)
                translated = translator.translate(text)
        except Exception as e:
            self.log_signal.emit(f"Lỗi khi dịch bằng {self.engine_type}: {e}. Đang thử fallback...")
            
            # 2. Fallback: Nếu Google lỗi thì thử MyMemory, nếu MyMemory lỗi thì thử Google
            try:
                fallback_engine = "MyMemory" if self.engine_type == "Google" else "Google"
                if fallback_engine == "Google":
                    translator = GoogleTranslator(source=src_code, target=dest_code)
                else:
                    mym_src = map_mymemory_lang_code(src_code)
                    mym_dest = map_mymemory_lang_code(dest_code)
                    translator = MyMemoryTranslator(source=mym_src, target=mym_dest)
                translated = translator.translate(text)
                self.log_signal.emit(f"Dịch thành công bằng dịch vụ dự phòng ({fallback_engine})")
            except Exception as fe:
                self.log_signal.emit(f"Cả hai dịch vụ dịch thuật đều thất bại: {fe}")
                translated = f"[Lỗi dịch thuật: Hãy kiểm tra mạng hoặc đổi dịch vụ dịch]"
                
        # Lưu vào cache nếu dịch thành công và không phải lỗi mạng
        if translated and not translated.startswith("[Lỗi"):
            self.translation_cache[cache_key] = translated
            
        return translated

    def preprocess_image(self, pil_image):
        """Tiền xử lý ảnh để nâng cao chất lượng nhận diện OCR."""
        # Chuyển sang ảnh grayscale (đen trắng)
        gray_img = pil_image.convert("L")
        
        # Tăng độ tương phản (làm nổi bật chữ trên nền)
        enhancer = ImageEnhance.Contrast(gray_img)
        enhanced_img = enhancer.enhance(2.0)
        
        # Có thể nghịch đảo màu nếu cần, nhưng Windows OCR tự nhận dạng tốt cả chữ sáng trên nền tối
        return enhanced_img

    def stop(self):
        """Dừng luồng xử lý."""
        self.running = False

    def run(self):
        import winrt._winrt as _w
        _w.init_apartment(_w.MTA)
        self.running = True
        self.log_signal.emit("Bắt đầu luồng dịch trực tiếp...")
        
        # Khởi tạo công cụ chụp màn hình mss
        sct = mss.mss()
        
        try:
            while self.running:
                start_time = time.time()
                
                # 1. Kiểm tra và khởi tạo OCR Engine nếu chưa có
                if self.ocr_engine is None:
                    try:
                        self.log_signal.emit(f"Đang khởi tạo OCR Engine cho ngôn ngữ: {self.src_lang}")
                        self.ocr_engine = WindowsOcrEngine(self.src_lang)
                        self.log_signal.emit("Khởi tạo OCR Engine thành công.")
                    except Exception as e:
                        self.log_signal.emit(f"LỖI: {e}")
                        self.translation_ready.emit(f"[Lỗi OCR: {e}]")
                        time.sleep(2.0) # Ngủ lâu hơn một chút trước khi thử lại
                        continue
                
                try:
                    # 2. Chụp màn hình vùng chỉ định
                    monitor = {"top": self.y, "left": self.x, "width": self.w, "height": self.h}
                    sct_img = sct.grab(monitor)
                    
                    # Chuyển đổi mss image sang Pillow Image
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    
                    # 3. Tiền xử lý ảnh để OCR tốt hơn
                    processed_img = self.preprocess_image(img)
                    
                    # 4. Thực hiện OCR
                    text = self.ocr_engine.recognize(processed_img).strip()
                    
                    # Làm sạch text (bỏ dòng trống dư thừa)
                    text_clean = "\n".join([line.strip() for line in text.split("\n") if line.strip()])
                    
                    # 5. So sánh xem chữ có thay đổi so với lần trước không
                    if text_clean != self.last_ocr_text:
                        self.last_ocr_text = text_clean
                        
                        if text_clean:
                            self.log_signal.emit(f"OCR phát hiện chữ mới: {text_clean.replace(chr(10), ' | ')}")
                            # Dịch chữ
                            translated = self.translate_text(text_clean)
                            self.translation_ready.emit(translated)
                        else:
                            # Nếu không có chữ, xóa ô hiển thị phụ đề dịch ngay lập tức
                            self.translation_ready.emit("")
                            
                except Exception as e:
                    self.log_signal.emit(f"Lỗi trong vòng lặp dịch: {e}")
                    
                # 6. Tính toán thời gian ngủ để duy trì giãn cách phù hợp
                elapsed = time.time() - start_time
                sleep_time = max(0.1, self.interval - elapsed)
                time.sleep(sleep_time)
        finally:
            # Đóng mss khi dừng luồng
            try:
                sct.close()
            except:
                pass
            _w.uninit_apartment()
            self.log_signal.emit("Đã dừng luồng dịch.")
