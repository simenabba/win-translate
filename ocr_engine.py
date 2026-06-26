import asyncio
import sys
from PIL import Image, ImageDraw, ImageFont
import winrt.windows.media.ocr as ocr
import winrt.windows.graphics.imaging as imaging
import winrt.windows.storage.streams as streams
from winrt.windows.globalization import Language

def get_supported_languages():
    """Trả về danh sách các language tag (ví dụ: 'en-US', 'ja-JP') được hỗ trợ bởi Windows OCR trên máy."""
    try:
        langs = ocr.OcrEngine.available_recognizer_languages
        return [lang.language_tag for lang in langs]
    except Exception as e:
        print(f"Lỗi khi lấy danh sách ngôn ngữ: {e}", file=sys.stderr)
        return []

class WindowsOcrEngine:
    def __init__(self, lang_tag="en-US"):
        self.lang_tag = lang_tag
        self.lang = Language(lang_tag)
        
        # Kiểm tra xem ngôn ngữ có được hỗ trợ OCR không
        if not ocr.OcrEngine.is_language_supported(self.lang):
            supported = get_supported_languages()
            msg = f"Ngôn ngữ '{lang_tag}' chưa được cài đặt gói OCR trên Windows."
            if supported:
                msg += f" Các ngôn ngữ đang hỗ trợ: {', '.join(supported)}"
            else:
                msg += " Vui lòng cài đặt gói ngôn ngữ trong Windows Settings."
            raise ValueError(msg)
            
        self.engine = ocr.OcrEngine.try_create_from_language(self.lang)
        if not self.engine:
            raise RuntimeError(f"Không thể khởi tạo Windows OCR Engine cho ngôn ngữ '{lang_tag}'")

    def _pillow_to_software_bitmap(self, pil_image):
        """Chuyển đổi PIL Image sang Windows SoftwareBitmap (RGBA8)."""
        # Đảm bảo ảnh ở định dạng RGBA
        img = pil_image.convert("RGBA")
        
        # Sử dụng DataWriter để chuyển đổi dữ liệu byte thành IBuffer
        data_writer = streams.DataWriter()
        data_writer.write_bytes(img.tobytes())
        
        bitmap = imaging.SoftwareBitmap(
            imaging.BitmapPixelFormat.RGBA8, 
            img.width, 
            img.height
        )
        bitmap.copy_from_buffer(data_writer.detach_buffer())
        return bitmap

    async def _recognize_async(self, pil_image):
        """Hàm bất đồng bộ thực hiện nhận diện chữ."""
        bitmap = self._pillow_to_software_bitmap(pil_image)
        result = await self.engine.recognize_async(bitmap)
        
        # Kết hợp các dòng văn bản
        text_lines = []
        for line in result.lines:
            text_lines.append(line.text)
        return "\n".join(text_lines)

    def recognize(self, pil_image):
        """Nhận diện văn bản từ PIL Image (Đồng bộ)."""
        try:
            # Tạo event loop mới cho thread hiện tại và thiết lập nó
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self._recognize_async(pil_image))
            finally:
                loop.close()
        except Exception as e:
            print(f"Lỗi khi thực hiện OCR: {e}", file=sys.stderr)
            return ""

# Tự động chạy thử nghiệm nếu chạy file này trực tiếp
if __name__ == "__main__":
    print("--- KIỂM TRA HỆ THỐNG WINDOWS OCR ---")
    supported_langs = get_supported_languages()
    print(f"Danh sách ngôn ngữ OCR được cài đặt: {supported_langs}")
    
    if not supported_langs:
        print("CẢNH BÁO: Không tìm thấy ngôn ngữ OCR nào được cài đặt trên Windows!")
        sys.exit(1)
        
    # Chọn ngôn ngữ đầu tiên có sẵn để test (ưu tiên en-US hoặc ngôn ngữ đầu danh sách)
    test_lang = "en-US" if "en-US" in supported_langs else supported_langs[0]
    print(f"Thử nghiệm OCR với ngôn ngữ: {test_lang}")
    
    try:
        ocr_engine = WindowsOcrEngine(test_lang)
        print("Khởi tạo WindowsOcrEngine thành công!")
        
        # Tạo ảnh nháp chứa chữ để test
        img = Image.new("RGBA", (400, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 35), "Hello World! WinOCR works.", fill="black")
        
        text = ocr_engine.recognize(img)
        print("\n--- KẾT QUẢ OCR ---")
        print(f"Văn bản nhận diện được:\n{text}")
        print("--------------------")
        if "Hello" in text or "World" in text or "OCR" in text or "works" in text:
            print("Kết quả: THÀNH CÔNG! Windows OCR đang hoạt động tốt.")
        else:
            print("Kết quả: THẤT BẠI! Không nhận dạng được chữ mẫu.")
            
    except Exception as e:
        print(f"Lỗi kiểm thử: {e}")
