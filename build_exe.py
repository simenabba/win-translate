import os
import subprocess
import sys

def build():
    print("--- WIN-TRANSLATE BUILD SYSTEM ---")
    
    # 1. Kiểm tra và cài đặt PyInstaller
    try:
        import PyInstaller
        print("[+] PyInstaller đã có sẵn trên máy.")
    except ImportError:
        print("[*] PyInstaller chưa được cài đặt. Đang tiến hành cài đặt...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("[+] Đã cài đặt PyInstaller thành công.")
        except Exception as e:
            print(f"[-] Không thể cài đặt PyInstaller: {e}")
            sys.exit(1)
            
    # 2. Cấu hình lệnh đóng gói
    # - --noconsole (hoặc -w): Ẩn cửa sổ Console màu đen khi phần mềm chạy
    # - --onefile (hoặc -F): Đóng gói tất cả thành một file .exe duy nhất để dễ chia sẻ
    # - --collect-all winrt: BẮT BUỘC để thu thập tất cả các module WinRT OCR tránh lỗi ClassNotFound khi chạy exe
    # - --name: Tên file exe đầu ra
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--collect-all", "winrt",
        "--icon=app_icon.ico",
        "--name", "win-translate",
        "main.py"
    ]
    
    print(f"[*] Bắt đầu đóng gói với lệnh: {' '.join(cmd)}")
    
    try:
        # Chạy lệnh đóng gói
        subprocess.check_call(cmd)
        
        print("\n" + "="*40)
        print("ĐÓNG GÓI THÀNH CÔNG CHƯƠNG TRÌNH!")
        print(f"File chạy .exe nằm ở thư mục: {os.path.abspath('dist/win-translate.exe')}")
        print("Bạn có thể copy file này đi bất kỳ máy Windows 10/11 nào để chạy trực tiếp.")
        print("="*40)
        
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Quá trình đóng gói thất bại với mã lỗi: {e}")
    except Exception as e:
        print(f"\n[-] Lỗi không xác định: {e}")

if __name__ == "__main__":
    build()
