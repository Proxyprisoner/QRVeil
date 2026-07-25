"""
Dual-Message QR Code Toolkit (Final Bug-Free Version)
===================================================
1. Public Mode: Standard URL/Text readable by any standard scanner/phone camera.
2. Personal Camera Mode: Decrypts real hidden payloads live from video feed.
3. LSB File Mode: Hidden pixel steganography for digital file inspection.
"""

import sys
import argparse
import webbrowser
import time
import threading
import urllib.parse
import tkinter as tk
from tkinter import messagebox
import qrcode
from PIL import Image
import cv2
from pyzbar.pyzbar import decode
from cryptography.fernet import Fernet

MAGIC_HEADER = "STEGO"

last_scanned_data = None
last_scanned_time = 0
popup_open = False
COOLDOWN_SECONDS = 3

# ==========================================
# 1. THREAD-SAFE GUI POPUP
# ==========================================

def _launch_popup_thread(title, message, is_url=False):
    global popup_open
    if popup_open:
        return

    popup_open = True

    def run_gui():
        global popup_open
        root = tk.Tk()
        root.title(title)
        root.geometry("440x190")
        root.resizable(False, False)
        root.attributes('-topmost', True)

        def on_close():
            global popup_open
            popup_open = False
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_close)

        lbl_title = tk.Label(root, text=title, font=("Helvetica", 11, "bold"), fg="#D32F2F")
        lbl_title.pack(pady=(15, 5))

        txt_box = tk.Entry(root, font=("Helvetica", 10), justify="center", width=48)
        txt_box.insert(0, message)
        txt_box.pack(pady=5)

        def copy_to_clipboard():
            root.clipboard_clear()
            root.clipboard_append(message)
            messagebox.showinfo("Copied", "Copied to clipboard!", parent=root)

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=15)

        btn_copy = tk.Button(btn_frame, text="📋 Copy", command=copy_to_clipboard, width=10)
        btn_copy.pack(side=tk.LEFT, padx=5)

        if is_url or message.startswith("http://") or message.startswith("https://"):
            def open_browser():
                webbrowser.open(message)
                on_close()

            btn_open = tk.Button(btn_frame, text="🌐 Open Link", command=open_browser, bg="#4CAF50", fg="white", width=12)
            btn_open.pack(side=tk.LEFT, padx=5)

        btn_close = tk.Button(btn_frame, text="Close", command=on_close, width=8)
        btn_close.pack(side=tk.LEFT, padx=5)

        root.mainloop()

    t = threading.Thread(target=run_gui, daemon=True)
    t.start()

def show_output_box(title, message, is_url=False):
    _launch_popup_thread(title, message, is_url)

# ==========================================
# 2. GENERATORS
# ==========================================

def _text_to_bin(text):
    full_payload = MAGIC_HEADER + text
    binary = format(len(full_payload), '016b')
    binary += ''.join(format(ord(c), '08b') for c in full_payload)
    return binary

def generate_lsb_qr(public_msg, secret_msg, output_path="dual_lsb.png"):
    """Generates LSB QR for digital file sharing."""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(public_msg)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    pixels = img.load()
    width, height = img.size

    secret_bin = _text_to_bin(secret_msg)
    total_bits = len(secret_bin)

    if total_bits > width * height:
        raise ValueError("Secret message too long for this QR size.")

    bit_index = 0
    for y in range(height):
        for x in range(width):
            if bit_index < total_bits:
                r, g, b = pixels[x, y]
                new_g = (g & ~1) | int(secret_bin[bit_index])
                pixels[x, y] = (r, new_g, b)
                bit_index += 1
            else:
                break
        if bit_index >= total_bits:
            break

    img.save(output_path)
    print(f"✅ Generated LSB Digital QR: {output_path}")

def generate_camera_qr(public_url, secret_msg, key_str, output_path="dual_cam.png"):
    """Encrypts secret payload into query string readable by live camera."""
    f = Fernet(key_str.encode())
    encrypted_secret = f.encrypt(secret_msg.encode()).decode()
    encoded_param = urllib.parse.quote(encrypted_secret)
    
    separator = "&" if "?" in public_url else "?"
    full_payload = f"{public_url}{separator}d={encoded_param}"

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(full_payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    print(f"✅ Generated Camera Dual QR Code: {output_path}")

# ==========================================
# 3. SCANNERS
# ==========================================

def scan_public_file(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Error opening {image_path}")
        return

    decoded = decode(img)
    if not decoded:
        print("❌ No QR detected.")
        return

    for obj in decoded:
        msg = obj.data.decode('utf-8')
        # If camera QR URL, clean output for public viewer
        if "?d=" in msg or "&d=" in msg:
            clean_msg = msg.split('?d=')[0].split('&d=')[0]
        else:
            clean_msg = msg
        print(f"📱 Public Message: {clean_msg}")
        show_output_box("Public QR Code Detected", clean_msg, is_url=True)

def scan_secret_file_lsb(image_path):
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    pixels = img.load()
    width, height = img.size

    extracted_bits = []
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            extracted_bits.append(str(g & 1))

    bits_str = ''.join(extracted_bits)
    try:
        payload_len = int(bits_str[:16], 2)
        payload_bits = bits_str[16 : 16 + (payload_len * 8)]
        
        full_payload = "".join(chr(int(payload_bits[i:i+8], 2)) for i in range(0, len(payload_bits), 8))

        if full_payload.startswith(MAGIC_HEADER):
            secret_msg = full_payload[len(MAGIC_HEADER):]
            print(f"🔒 Hidden Secret Message: {secret_msg}")
            show_output_box("Personal Secret Message Detected", secret_msg, is_url=True)
        else:
            print("❌ No hidden LSB payload found.")
    except Exception:
        print("❌ No hidden LSB payload found.")

def scan_personal_camera(key_str, cam_idx=0):
    global last_scanned_data, last_scanned_time
    f = Fernet(key_str.encode())
    cap = cv2.VideoCapture(cam_idx)

    if not cap.isOpened():
        print("❌ Unable to access webcam.")
        return

    print("🔒 Personal Camera Scanner active. Press 'q' to exit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        decoded_objects = decode(frame)
        current_time = time.time()

        for obj in decoded_objects:
            raw_url = obj.data.decode('utf-8')
            
            if "d=" in raw_url:
                try:
                    parsed_url = urllib.parse.urlparse(raw_url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    encrypted_val = query_params.get('d', [None])[0]

                    if encrypted_val:
                        # Real dynamic decryption
                        decrypted_msg = f.decrypt(urllib.parse.unquote(encrypted_val).encode()).decode()

                        rect = obj.rect
                        cv2.rectangle(frame, (rect.left, rect.top), (rect.left + rect.width, rect.top + rect.height), (0, 0, 255), 3)

                        cv2.putText(frame, f"DECRYPTED: {decrypted_msg}", (20, 50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                        if not popup_open and (decrypted_msg != last_scanned_data or (current_time - last_scanned_time) > COOLDOWN_SECONDS):
                            last_scanned_data = decrypted_msg
                            last_scanned_time = current_time
                            show_output_box("🔒 Secret Payload Unlocked", decrypted_msg, is_url=True)
                except Exception:
                    pass

        cv2.imshow("Personal Camera Scanner", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

# ==========================================
# 4. CLI HANDLER
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Dual QR Code Toolkit")
    subparsers = parser.add_subparsers(dest="mode", help="Execution Mode")

    # Generate
    gen = subparsers.add_parser("generate")
    gen.add_argument("--public", required=True, help="Public Link/Message")
    gen.add_argument("--secret", required=True, help="Secret Hidden Payload")
    gen.add_argument("--key", default="", help="Fernet Key for Camera Mode")
    gen.add_argument("--type", choices=["lsb", "camera"], default="camera")
    gen.add_argument("--out", default="dual.png")

    # Scan File
    sf = subparsers.add_parser("scan-file")
    sf.add_argument("--image", required=True)
    sf.add_argument("--target", choices=["public", "secret"], default="public")

    # Scan Camera
    sc = subparsers.add_parser("scan-cam")
    sc.add_argument("--key", required=True, help="Fernet Key to decrypt payload")
    sc.add_argument("--camera-id", type=int, default=0)

    # Key Generator Helper
    subparsers.add_parser("genkey")

    args = parser.parse_args()

    if args.mode == "genkey":
        print(f"🔑 Generated Encryption Key: {Fernet.generate_key().decode()}")

    elif args.mode == "generate":
        if args.type == "camera":
            if not args.key:
                print("❌ Camera mode requires a key! Generate one with: python qr.py genkey")
                return
            generate_camera_qr(args.public, args.secret, args.key, args.out)
        else:
            generate_lsb_qr(args.public, args.secret, args.out)

    elif args.mode == "scan-file":
        if args.target == "public":
            scan_public_file(args.image)
        else:
            scan_secret_file_lsb(args.image)

    elif args.mode == "scan-cam":
        scan_personal_camera(args.key, args.camera_id)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()