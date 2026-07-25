"""
Dual-Message QR Code Desktop App (Final Stable Build)
===================================================
- Native Tkinter Video Display Canvas (Zero PyImage GC Leaks / Zero Tcl Errors).
- Reliable Re-startable OpenCV Video Capture Loop.
- Real-time Encryption Payload Decryption & LSB Steganography.
"""

import urllib.parse
import time
import webbrowser
import tkinter as tk
from PIL import Image, ImageTk
import cv2
from cryptography.fernet import Fernet
import customtkinter as ctk
import qrcode

MAGIC_HEADER = "STEGO"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ==========================================
# CORE HELPERS
# ==========================================

def text_to_bin(text: str) -> str:
    full_payload = MAGIC_HEADER + text
    binary = format(len(full_payload), '016b')
    binary += ''.join(format(ord(c), '08b') for c in full_payload)
    return binary

def create_lsb_qr(public_msg: str, secret_msg: str, output_path: str = "dual_lsb.png"):
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(public_msg)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    pixels = img.load()
    width, height = img.size

    secret_bin = text_to_bin(secret_msg)
    total_bits = len(secret_bin)

    if total_bits > width * height:
        raise ValueError("Secret payload is too long for this QR size.")

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

def create_camera_qr(public_url: str, secret_msg: str, key_str: str, output_path: str = "dual.png"):
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

# ==========================================
# APPLICATION CLASS
# ==========================================

class DualQRApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Dual-Message QR Toolkit")
        self.geometry("820x720")
        self.resizable(False, False)

        # Camera States
        self.camera_running = False
        self.cap = None
        self.qr_detector = cv2.QRCodeDetector()
        self.last_scanned = ""
        self.last_time = 0

        # Title
        self.lbl_main = ctk.CTkLabel(
            self, text="📱 Dual-Message QR Code System", 
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold")
        )
        self.lbl_main.pack(pady=(15, 10))

        # Tabs
        self.tabview = ctk.CTkTabview(self, width=780, height=480)
        self.tabview.pack(padx=20, pady=5)

        self.tab_gen = self.tabview.add("Generator")
        self.tab_file = self.tabview.add("File Scanner")
        self.tab_cam = self.tabview.add("Camera Scanner")

        self._build_generator_tab()
        self._build_file_tab()
        self._build_camera_tab()

        # Shared Result Output Box
        self.frame_result = ctk.CTkFrame(self, width=780, height=130, fg_color="#1E1E2E")
        self.frame_result.pack(padx=20, pady=(10, 15), fill="x")

        self.lbl_result_title = ctk.CTkLabel(
            self.frame_result, text="Decoded Output / Status:", 
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#AAAAAA"
        )
        self.lbl_result_title.pack(anchor="w", padx=15, pady=(10, 2))

        self.entry_result = ctk.CTkEntry(
            self.frame_result, width=740, height=36,
            font=ctk.CTkFont(family="Consolas", size=13),
            justify="center"
        )
        self.entry_result.pack(padx=15, pady=5)

        self.frame_actions = ctk.CTkFrame(self.frame_result, fg_color="transparent")
        self.frame_actions.pack(pady=(2, 10))

        self.btn_copy = ctk.CTkButton(
            self.frame_actions, text="📋 Copy", command=self._copy_result, width=100,
            fg_color="#333333", hover_color="#444444"
        )
        self.btn_copy.pack(side="left", padx=5)

        self.btn_open_link = ctk.CTkButton(
            self.frame_actions, text="🌐 Open Link", command=self._open_result_link, width=110,
            fg_color="#2E7D32", hover_color="#1B5E20"
        )
        self.btn_open_link.pack(side="left", padx=5)

    # ------------------------------------------
    # TAB 1: GENERATOR
    # ------------------------------------------
    def _build_generator_tab(self):
        lbl_pub = ctk.CTkLabel(self.tab_gen, text="Public Message / URL:")
        lbl_pub.pack(anchor="w", padx=20, pady=(10, 2))
        self.entry_pub = ctk.CTkEntry(self.tab_gen, width=700, placeholder_text="https://example.com/welcome")
        self.entry_pub.pack(padx=20, pady=2)

        lbl_sec = ctk.CTkLabel(self.tab_gen, text="Secret Hidden Payload:")
        lbl_sec.pack(anchor="w", padx=20, pady=(8, 2))
        self.entry_sec = ctk.CTkEntry(self.tab_gen, width=700, placeholder_text="CONFIDENTIAL_DATA_123")
        self.entry_sec.pack(padx=20, pady=2)

        lbl_key = ctk.CTkLabel(self.tab_gen, text="Encryption Key (Camera Mode):")
        lbl_key.pack(anchor="w", padx=20, pady=(8, 2))

        frame_key = ctk.CTkFrame(self.tab_gen, fg_color="transparent")
        frame_key.pack(fill="x", padx=20, pady=2)

        self.entry_key = ctk.CTkEntry(frame_key, width=540, placeholder_text="Paste or generate Fernet key")
        self.entry_key.pack(side="left", padx=(0, 10))

        btn_gen_key = ctk.CTkButton(frame_key, text="🔑 New Key", command=self._generate_key, width=140)
        btn_gen_key.pack(side="left")

        self.var_type = ctk.StringVar(value="camera")
        frame_radio = ctk.CTkFrame(self.tab_gen, fg_color="transparent")
        frame_radio.pack(anchor="w", padx=20, pady=12)

        radio_cam = ctk.CTkRadioButton(frame_radio, text="Camera Dual QR (URL Encrypted)", variable=self.var_type, value="camera")
        radio_cam.pack(side="left", padx=(0, 20))

        radio_lsb = ctk.CTkRadioButton(frame_radio, text="LSB Steganography (File Only)", variable=self.var_type, value="lsb")
        radio_lsb.pack(side="left")

        btn_gen_qr = ctk.CTkButton(
            self.tab_gen, text="⚡ Generate QR Code", command=self._generate_qr, 
            height=40, font=ctk.CTkFont(size=14, weight="bold")
        )
        btn_gen_qr.pack(pady=15)

    def _generate_key(self):
        new_key = Fernet.generate_key().decode()
        self.entry_key.delete(0, "end")
        self.entry_key.insert(0, new_key)
        self.entry_cam_key.delete(0, "end")
        self.entry_cam_key.insert(0, new_key)
        self.update_result(f"Key Generated: {new_key}", is_secret=False)

    def _generate_qr(self):
        pub = self.entry_pub.get().strip()
        sec = self.entry_sec.get().strip()
        key = self.entry_key.get().strip()
        mode = self.var_type.get()

        if not pub or not sec:
            self.update_result("❌ Error: Both Public and Secret fields are required!", is_secret=True)
            return

        try:
            if mode == "camera":
                if not key:
                    self.update_result("❌ Error: Camera mode requires an encryption key!", is_secret=True)
                    return
                create_camera_qr(pub, sec, key, "dual.png")
                self.update_result("✅ Successfully generated 'dual.png' (Camera Mode)", is_secret=False)
            else:
                create_lsb_qr(pub, sec, "dual_lsb.png")
                self.update_result("✅ Successfully generated 'dual_lsb.png' (LSB Mode)", is_secret=False)
        except Exception as e:
            self.update_result(f"❌ Error: {str(e)}", is_secret=True)

    # ------------------------------------------
    # TAB 2: FILE SCANNER
    # ------------------------------------------
    def _build_file_tab(self):
        lbl_file = ctk.CTkLabel(self.tab_file, text="Select Image File to Decode:")
        lbl_file.pack(anchor="w", padx=20, pady=(20, 5))

        frame_file_input = ctk.CTkFrame(self.tab_file, fg_color="transparent")
        frame_file_input.pack(fill="x", padx=20, pady=5)

        self.entry_filepath = ctk.CTkEntry(frame_file_input, width=540, placeholder_text="Path to image (e.g. dual.png)")
        self.entry_filepath.pack(side="left", padx=(0, 10))

        btn_browse = ctk.CTkButton(frame_file_input, text="📁 Browse", command=self._browse_file, width=140)
        btn_browse.pack(side="left")

        frame_scan_btns = ctk.CTkFrame(self.tab_file, fg_color="transparent")
        frame_scan_btns.pack(pady=30)

        btn_scan_pub = ctk.CTkButton(
            frame_scan_btns, text="📱 Scan Public QR", command=self._scan_public_file, 
            width=180, height=40, fg_color="#2E7D32", hover_color="#1B5E20"
        )
        btn_scan_pub.pack(side="left", padx=10)

        btn_scan_sec = ctk.CTkButton(
            frame_scan_btns, text="🔒 Scan Secret LSB", command=self._scan_secret_file, 
            width=180, height=40, fg_color="#D32F2F", hover_color="#9A0007"
        )
        btn_scan_sec.pack(side="left", padx=10)

    def _browse_file(self):
        filename = ctk.filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg")])
        if filename:
            self.entry_filepath.delete(0, "end")
            self.entry_filepath.insert(0, filename)

    def _scan_public_file(self):
        path = self.entry_filepath.get().strip()
        if not path:
            self.update_result("❌ Please select a file first.", is_secret=True)
            return

        img = cv2.imread(path)
        if img is None:
            self.update_result("❌ Could not open image file.", is_secret=True)
            return

        raw_url, _, _ = self.qr_detector.detectAndDecode(img)
        if raw_url:
            clean_msg = raw_url.split('?d=')[0].split('&d=')[0] if "d=" in raw_url else raw_url
            self.update_result(clean_msg, is_secret=False)
        else:
            self.update_result("❌ No valid QR code found in file.", is_secret=True)

    def _scan_secret_file(self):
        path = self.entry_filepath.get().strip()
        if not path:
            self.update_result("❌ Please select a file first.", is_secret=True)
            return

        try:
            img = Image.open(path).convert("RGB")
            pixels = img.load()
            width, height = img.size

            extracted_bits = [str(pixels[x, y][1] & 1) for y in range(height) for x in range(width)]
            bits_str = ''.join(extracted_bits)

            payload_len = int(bits_str[:16], 2)
            payload_bits = bits_str[16 : 16 + (payload_len * 8)]
            full_payload = "".join(chr(int(payload_bits[i:i+8], 2)) for i in range(0, len(payload_bits), 8))

            if full_payload.startswith(MAGIC_HEADER):
                secret_msg = full_payload[len(MAGIC_HEADER):]
                self.update_result(secret_msg, is_secret=True)
            else:
                self.update_result("❌ No hidden LSB payload found in file.", is_secret=True)
        except Exception:
            self.update_result("❌ Failed to decode LSB secret payload.", is_secret=True)

    # ------------------------------------------
    # TAB 3: CAMERA SCANNER
    # ------------------------------------------
    def _build_camera_tab(self):
        lbl_cam_key = ctk.CTkLabel(self.tab_cam, text="Decryption Key for Camera Mode:")
        lbl_cam_key.pack(anchor="w", padx=20, pady=(10, 2))

        self.entry_cam_key = ctk.CTkEntry(self.tab_cam, width=700, placeholder_text="Paste encryption key here")
        self.entry_cam_key.pack(padx=20, pady=2)

        frame_cam_opt = ctk.CTkFrame(self.tab_cam, fg_color="transparent")
        frame_cam_opt.pack(anchor="w", padx=20, pady=5)

        lbl_cam_idx = ctk.CTkLabel(frame_cam_opt, text="Camera Index:")
        lbl_cam_idx.pack(side="left", padx=(0, 10))

        self.combo_cam_idx = ctk.CTkOptionMenu(frame_cam_opt, values=["0", "1", "2"], width=70)
        self.combo_cam_idx.pack(side="left", padx=(0, 20))

        self.lbl_cam_status = ctk.CTkLabel(frame_cam_opt, text="○ Camera Stopped", text_color="#888888", font=ctk.CTkFont(weight="bold"))
        self.lbl_cam_status.pack(side="left")

        # NATIVE TKINTER LABEL FOR VIDEO (Prevents CustomTkinter GC pyimage bugs)
        self.lbl_video = tk.Label(
            self.tab_cam, text="[ Camera Feed Inactive ]", 
            bg="#111118", fg="#888888", font=("Segoe UI", 11)
        )
        self.lbl_video.pack(pady=10, ipadx=180, ipady=80)

        frame_cam_ctrl = ctk.CTkFrame(self.tab_cam, fg_color="transparent")
        frame_cam_ctrl.pack()

        self.btn_start_cam = ctk.CTkButton(
            frame_cam_ctrl, text="▶ Start Camera", command=self._start_camera, width=160
        )
        self.btn_start_cam.pack(side="left", padx=10)

        self.btn_stop_cam = ctk.CTkButton(
            frame_cam_ctrl, text="⏹ Stop Camera", command=self._stop_camera, width=160,
            fg_color="#D32F2F", hover_color="#9A0007", state="disabled"
        )
        self.btn_stop_cam.pack(side="left", padx=10)

    def _start_camera(self):
        if self.camera_running:
            return

        key_str = self.entry_cam_key.get().strip()
        if not key_str:
            self.update_result("❌ Error: Decryption key is required for live camera mode!", is_secret=True)
            return

        try:
            self.fernet = Fernet(key_str.encode())
        except Exception:
            self.update_result("❌ Invalid key format! Generate a key from the Generator tab first.", is_secret=True)
            return

        cam_idx = int(self.combo_cam_idx.get())

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        # Try DirectShow for Windows fast-init, fallback to default
        self.cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(cam_idx)

        if not self.cap.isOpened():
            self.update_result(f"❌ Could not open camera index {cam_idx}. Try index 1 or 2.", is_secret=True)
            return

        # Pre-test reading 1 frame from hardware
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.cap.release()
            self.cap = None
            self.update_result(f"❌ Camera at index {cam_idx} opened but produced no frame.", is_secret=True)
            return

        self.camera_running = True
        self.btn_start_cam.configure(state="disabled")
        self.btn_stop_cam.configure(state="normal")
        self.lbl_cam_status.configure(text="● Camera Active", text_color="#00FF66")

        # Kickoff Native Mainloop Video Tick
        self._update_camera_frame()

    def _stop_camera(self):
        self.camera_running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.btn_start_cam.configure(state="normal")
        self.btn_stop_cam.configure(state="disabled")
        self.lbl_cam_status.configure(text="○ Camera Stopped", text_color="#888888")
        
        # Reset display
        self.lbl_video.config(image="", text="[ Camera Feed Inactive ]")
        self.lbl_video.image = None

    def _update_camera_frame(self):
        """Single-threaded, zero-leak native Tkinter camera event tick."""
        if not self.camera_running or self.cap is None:
            return

        ret, frame = self.cap.read()
        if ret and frame is not None:
            # Color Pass
            raw_url, points, _ = self.qr_detector.detectAndDecode(frame)

            # Grayscale Fallback
            if not raw_url:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                raw_url, points, _ = self.qr_detector.detectAndDecode(gray)

            # Draw green bounding box around detected QR code
            if points is not None and len(points) > 0:
                pts = points[0].astype(int)
                for i in range(len(pts)):
                    cv2.line(frame, tuple(pts[i]), tuple(pts[(i + 1) % len(pts)]), (0, 255, 0), 3)

            # Decrypt Payload
            if raw_url and "d=" in raw_url:
                current_time = time.time()
                try:
                    parsed_url = urllib.parse.urlparse(raw_url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    encrypted_val = query_params.get('d', [None])[0]

                    if encrypted_val:
                        decrypted_msg = self.fernet.decrypt(urllib.parse.unquote(encrypted_val).encode()).decode()

                        if decrypted_msg != self.last_scanned or (current_time - self.last_time) > 3:
                            self.last_scanned = decrypted_msg
                            self.last_time = current_time
                            self.update_result(decrypted_msg, is_secret=True)
                except Exception as e:
                    self.update_result(f"❌ Key Mismatch: Could not decrypt ({str(e)})", is_secret=True)

            # Direct ImageTk PhotoImage binding (No memory leak/pyimage crash)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame).resize((500, 210))
            img_tk = ImageTk.PhotoImage(image=pil_img)

            self.lbl_video.config(image=img_tk, text="")
            self.lbl_video.image = img_tk  # Keep strong reference to prevent GC deletion

        # Schedule next tick in 30ms (~33 FPS)
        if self.camera_running:
            self.after(30, self._update_camera_frame)

    # ------------------------------------------
    # OUTPUT DISPLAY
    # ------------------------------------------
    def update_result(self, text, is_secret=False):
        self.entry_result.configure(state="normal")
        self.entry_result.delete(0, "end")
        self.entry_result.insert(0, text)
        self.entry_result.configure(state="readonly")

        if is_secret:
            self.lbl_result_title.configure(text="🔒 Decrypted Secret Payload:", text_color="#FF5252")
        else:
            self.lbl_result_title.configure(text="📱 Public Output / Status:", text_color="#4CAF50")

    def _copy_result(self):
        text = self.entry_result.get()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.btn_copy.configure(text="✓ Copied!")
            self.after(1500, lambda: self.btn_copy.configure(text="📋 Copy"))

    def _open_result_link(self):
        text = self.entry_result.get()
        if text.startswith("http://") or text.startswith("https://"):
            webbrowser.open(text)

    def on_closing(self):
        self._stop_camera()
        self.destroy()

if __name__ == "__main__":
    app = DualQRApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()