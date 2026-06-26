import time
import sys
import queue
import numpy as np
import speech_recognition as sr
from PyQt6.QtCore import QThread, pyqtSignal
from deep_translator import GoogleTranslator, MyMemoryTranslator
from translator_thread import map_lang_code, map_mymemory_lang_code
import warnings
import threading
warnings.filterwarnings("ignore", message=".*discontinuity in recording.*")

def get_soundcard_loopback_mic():
    """Tìm thiết bị Loopback của card âm thanh (WASAPI) tương ứng với loa mặc định."""
    try:
        import soundcard as sc
        default_speaker = sc.default_speaker()
        if not default_speaker:
            return None
            
        mics = sc.all_microphones(include_loopback=True)
        
        # 1. Tìm thiết bị loopback tương ứng có tên khớp với default speaker
        for mic in mics:
            if getattr(mic, 'isloopback', False) and default_speaker.name in mic.name:
                return mic
                
        # 2. Fallback: tìm thiết bị loopback đầu tiên
        for mic in mics:
            if getattr(mic, 'isloopback', False):
                return mic
                
        return sc.default_microphone()
    except Exception as e:
        print(f"Lỗi khi tìm thiết bị âm thanh: {e}", file=sys.stderr)
        return None

class AudioWorker(threading.Thread):
    """Luồng phụ chuyên xử lý nhận diện giọng nói (STT) và dịch thuật từ hàng đợi dữ liệu âm thanh."""
    def __init__(self, recognizer, src_lang, dest_lang, engine_type, cache_dict, translation_ready_signal, log_signal):
        super().__init__()
        self.recognizer = recognizer
        self.src_lang = src_lang
        self.dest_lang = dest_lang
        self.engine_type = engine_type
        self.translation_cache = cache_dict
        self.translation_ready_signal = translation_ready_signal
        self.log_signal = log_signal
        
        self.job_queue = queue.Queue()
        self.running = False
        self.daemon = True
        self.sentence_counter = 1

    def add_job(self, audio_data):
        """Đẩy gói dữ liệu âm thanh vào hàng đợi để xử lý tuần tự."""
        self.job_queue.put(audio_data)

    def update_config(self, src_lang, dest_lang, engine_type):
        """Cập nhật cấu hình dịch."""
        self.src_lang = src_lang
        self.dest_lang = dest_lang
        self.engine_type = engine_type

    def translate_text(self, text):
        """Dịch văn bản bằng dịch vụ đã cấu hình."""
        if not text.strip():
            return ""
            
        cache_key = (self.src_lang, self.dest_lang, self.engine_type, text)
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
            
        src_code = map_lang_code(self.src_lang)
        dest_code = map_lang_code(self.dest_lang)
        src_stt_code = src_code.split('-')[0]
        
        translated = ""
        try:
            if self.engine_type == "Google":
                translator = GoogleTranslator(source=src_stt_code, target=dest_code)
                translated = translator.translate(text)
            elif self.engine_type == "MyMemory":
                mym_src = map_mymemory_lang_code(src_stt_code)
                mym_dest = map_mymemory_lang_code(dest_code)
                translator = MyMemoryTranslator(source=mym_src, target=mym_dest)
                translated = translator.translate(text)
        except Exception as e:
            self.log_signal.emit(f"Audio: Lỗi dịch bằng {self.engine_type}: {e}. Đang thử fallback...")
            try:
                fallback_engine = "MyMemory" if self.engine_type == "Google" else "Google"
                if fallback_engine == "Google":
                    translator = GoogleTranslator(source=src_stt_code, target=dest_code)
                else:
                    mym_src = map_mymemory_lang_code(src_stt_code)
                    mym_dest = map_mymemory_lang_code(dest_code)
                    translator = MyMemoryTranslator(source=mym_src, target=mym_dest)
                translated = translator.translate(text)
                self.log_signal.emit(f"Audio: Dịch thành công bằng dịch vụ dự phòng ({fallback_engine})")
            except Exception as fe:
                self.log_signal.emit(f"Audio: Cả hai dịch vụ dịch thuật đều thất bại: {fe}")
                translated = f"[Lỗi dịch âm thanh]"
                
        if translated and not translated.startswith("[Lỗi"):
            self.translation_cache[cache_key] = translated
            
        return translated

    def stop(self):
        """Dừng worker thread."""
        self.running = False

    def run(self):
        self.running = True
        self.log_signal.emit("Audio Worker: Luồng nhận dạng STT đã khởi động thành công.")
        while self.running:
            try:
                # Lấy dữ liệu âm thanh từ hàng đợi (chờ tối đa 500ms)
                audio_data = self.job_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                stt_lang = self.src_lang
                self.log_signal.emit("Audio: Đang gửi âm thanh lên Google STT để nhận dạng...")
                
                # 1. Gọi Google Speech Recognition (API mạng đồng bộ - tốn khoảng 1-2s)
                text = self.recognizer.recognize_google(audio_data, language=stt_lang).strip()
                
                if text:
                    self.log_signal.emit(f"Audio STT nhận diện [{self.sentence_counter}]: {text}")
                    # 2. Gọi dịch thuật (API mạng đồng bộ - tốn khoảng 0.5-1s)
                    translated = self.translate_text(text)
                    if translated:
                        self.translation_ready_signal.emit(f"[{self.sentence_counter}] {text}\n→ {translated}")
                        self.sentence_counter += 1
                else:
                    self.log_signal.emit("Audio: Không có văn bản nào được nhận diện.")
            except sr.UnknownValueError:
                self.log_signal.emit("Audio: Google STT không nhận dạng được từ nào trong đoạn này.")
            except sr.RequestError as e:
                self.log_signal.emit(f"Audio STT lỗi kết nối API: {e}")
            except Exception as e:
                self.log_signal.emit(f"Lỗi trong worker dịch âm thanh: {e}")
            finally:
                self.job_queue.task_done()


class AudioTranslatorThread(QThread):
    """Luồng phụ chuyên trách ghi âm liên tục từ card âm thanh (không bị chặn bởi cuộc gọi API mạng)."""
    translation_ready = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self, src_lang="en-US", dest_lang="vi", engine_type="Google", threshold=0.001, silence_timeout=0.8):
        super().__init__()
        self.src_lang = src_lang
        self.dest_lang = dest_lang
        self.engine_type = engine_type
        
        # Cấu hình phát hiện giọng nói
        self.threshold = threshold              # Ngưỡng năng lượng âm thanh (RMS)
        self.silence_timeout = silence_timeout  # Thời gian im lặng tối đa để ngắt câu
        self.sample_rate = 16000                # Tần số lấy mẫu (16kHz)
        
        self.running = False
        self.recognizer = sr.Recognizer()
        self.translation_cache = {}
        self.worker = None

    def update_config(self, src_lang, dest_lang, engine_type):
        """Cập nhật cấu hình ngôn ngữ."""
        self.dest_lang = dest_lang
        self.engine_type = engine_type
        if self.src_lang != src_lang:
            self.src_lang = src_lang
        self.translation_cache.clear()
        
        if self.worker:
            self.worker.update_config(src_lang, dest_lang, engine_type)
        self.log_signal.emit(f"Audio: Cấu hình mới - Nguồn={src_lang}, Đích={dest_lang}, Engine={engine_type}")

    def stop(self):
        """Dừng ghi âm và worker thread."""
        self.running = False
        
        if self.worker:
            self.worker.stop()

    def run(self):
        self.running = True
        self.log_signal.emit("Khởi tạo luồng ghi âm hệ thống liên tục...")
        
        # 1. Khởi động Worker Thread chuyên xử lý API STT và Dịch ngầm
        self.worker = AudioWorker(
            self.recognizer, self.src_lang, self.dest_lang, 
            self.engine_type, self.translation_cache,
            self.translation_ready, self.log_signal
        )
        self.worker.start()
        
        # 2. Tìm thiết bị loopback mic bằng soundcard
        loopback_mic = get_soundcard_loopback_mic()
        if loopback_mic is None:
            self.log_signal.emit("LỖI: Không tìm thấy thiết bị âm thanh loopback phù hợp.")
            self.translation_ready.emit("[Không tìm thấy loa/tai nghe loopback]")
            if self.worker:
                self.worker.stop()
            return
            
        self.log_signal.emit(f"Đang sử dụng thiết bị loopback: {loopback_mic.name}")
        
        try:
            import soundcard as sc
            # 3. Mở luồng thu âm (Ghi âm đồng bộ 100ms liên tục)
            with loopback_mic.recorder(samplerate=self.sample_rate) as r:
                self.log_signal.emit("Đang ghi âm loopback từ card âm thanh hệ thống...")
                audio_buffer = []
                is_speaking = False
                last_active_time = time.time()
                last_volume_log_time = time.time()
                speaking_start_time = time.time()
                block_size = int(self.sample_rate * 0.5) # 500ms mỗi block
                
                while self.running:
                    # Ghi âm 500ms (blocking call 500ms, không tốn tài nguyên)
                    chunk = r.record(numframes=block_size)
                    
                    # Trộn Stereo thành Mono
                    if chunk.shape[1] > 1:
                        mono = np.mean(chunk, axis=1, keepdims=True)
                    else:
                        mono = chunk
                    
                    # Tính RMS của block hiện tại
                    rms = np.sqrt(np.mean(mono**2))
                    
                    if rms > self.threshold:
                        if not is_speaking:
                            is_speaking = True
                            speaking_start_time = time.time()
                            self.log_signal.emit(f"Audio: Phát hiện giọng nói... (Volume RMS: {rms:.4f}, Ngưỡng: {self.threshold})")
                        last_active_time = time.time()
                        audio_buffer.append(mono)
                        
                        # Giới hạn độ dài tối đa của một đoạn ghi âm (6 giây) để tránh dịch trễ khi có nhạc nền liên tục
                        if time.time() - speaking_start_time > 6.0:
                            self.log_signal.emit("Audio: Đạt độ dài tối đa (6.0s), tự động gửi đi dịch...")
                            self.queue_audio_for_translation(audio_buffer)
                            audio_buffer = []
                            speaking_start_time = time.time()
                    else:
                        if is_speaking:
                            audio_buffer.append(mono)
                            # Đã kết thúc một câu nói (quá khoảng lặng)
                            if time.time() - last_active_time > self.silence_timeout:
                                self.queue_audio_for_translation(audio_buffer)
                                audio_buffer = []
                                is_speaking = False
                        
                        # In cường độ âm thanh định kỳ mỗi 3 giây khi không phát hiện giọng nói
                        now = time.time()
                        if now - last_volume_log_time > 3.0:
                            self.log_signal.emit(f"Cường độ âm thanh hiện tại (RMS): {rms:.5f} | Ngưỡng kích hoạt: {self.threshold}")
                            last_volume_log_time = now
                                
                # Xử lý phần còn lại trong buffer khi dừng
                if is_speaking and audio_buffer:
                    self.queue_audio_for_translation(audio_buffer)
                    
        except Exception as e:
            self.log_signal.emit(f"LỖI trong luồng ghi âm liên tục: {e}")
            self.translation_ready.emit(f"[Lỗi âm thanh: {e}]")
            if self.worker:
                self.worker.stop()
            return

    def queue_audio_for_translation(self, audio_buffer):
        """Đóng gói dữ liệu âm thanh thô và đẩy vào hàng đợi của Worker Thread (Mất 0.000 giây)."""
        if not audio_buffer or not self.worker:
            return
            
        # Ghép các chunk thành một mảng numpy duy nhất
        concatenated = np.concatenate(audio_buffer, axis=0)
        flat_data = concatenated.flatten()
        
        # Chỉ xử lý nếu đoạn âm thanh tối thiểu dài hơn 0.5s
        if len(flat_data) < self.sample_rate * 0.5:
            return
            
        # Chuyển đổi sang PCM 16-bit
        audio_data_int16 = (flat_data * 32767).astype(np.int16)
        raw_bytes = audio_data_int16.tobytes()
        
        # Tạo đối tượng AudioData
        audio_data = sr.AudioData(raw_bytes, sample_rate=self.sample_rate, sample_width=2)
        
        # Gửi sang Worker Thread xử lý ngầm (Không block luồng ghi âm)
        self.log_signal.emit(f"Audio: Đã gửi đoạn âm thanh ({len(flat_data)/self.sample_rate:.1f}s) vào hàng đợi STT...")
        self.worker.add_job(audio_data)

# Chạy thử độc lập
if __name__ == "__main__":
    print("--- KIỂM TRA HỆ THỐNG THU ÂM HỆ THỐNG (QUEUE MULTI-THREAD) ---")
    loopback = get_soundcard_loopback_mic()
    if loopback is None:
        print("LỖI: Không tìm thấy thiết bị loopback nào.")
        sys.exit(1)
        
    print(f"Thiết bị loopback tìm được: {loopback.name}")
    thread = AudioTranslatorThread(src_lang="en-US", dest_lang="vi")
    
    def on_log(msg):
        print(f"[LOG] {msg}")
    def on_trans(text):
        print(f"\n[BẢN DỊCH ÂM THANH]: {text}\n")
        
    thread.log_signal.connect(on_log)
    thread.translation_ready.connect(on_trans)
    
    thread.start()
    print("Đang lắng nghe... Hãy mở một clip tiếng Anh trên máy tính để thử nghiệm. Nhấn Ctrl+C để dừng.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Đang dừng...")
        thread.stop()
