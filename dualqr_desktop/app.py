"""
Dual-Message QR Tool — GUI edition
-----------------------------------
Same exact logic as the original CLI script (all functions below are
byte-for-byte the same). Only the interaction layer changed: instead of
input()/print() in a terminal loop, there's now a Tkinter desktop UI.
"""

import base64
import hashlib
import os
import threading
import time
import urllib.parse

import qrcode
import cv2
from cryptography.fernet import Fernet

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk


# ======================================================================
# CORE LOGIC — unchanged from the original script
# ======================================================================

def generate_key() -> str:
    """Generates a random AES-256 Fernet key string."""
    return Fernet.generate_key().decode('utf-8')


def key_from_names(creator: str, friend: str, salt: bytes = b"dual-qr-fixed-salt") -> str:
    """
    Derives a valid, repeatable Fernet key from TWO names (creator + friend).
    Order-independent: key_from_names("Vishal", "Arun") ==
                        key_from_names("Arun", "Vishal")
    so either person can regenerate the same real key later.

    This is the ACTUAL key used for encryption/decryption -- it's a normal
    random-looking base64 string, same as any Fernet key.

    Note: two plain names alone is still a fairly weak secret (guessable if
    someone knows you two are exchanging QR codes). For anything beyond
    casual/fun use, add a shared suffix only you two know, e.g.
    key_from_names("vishal-blue42", "arun").
    """
    names_sorted = sorted([creator.strip().lower(), friend.strip().lower()])
    combined = "-".join(names_sorted)

    derived = hashlib.pbkdf2_hmac(
        'sha256',
        combined.encode('utf-8'),
        salt,
        390_000,
        dklen=32
    )
    return base64.urlsafe_b64encode(derived).decode('utf-8')


def display_key(creator: str, friend: str, real_key: str) -> str:
    """
    Builds a COSMETIC, fun-looking string that visibly embeds both names
    (e.g. "388dhhdVISHAL(@ARUNcgJk="), for sharing/showing off purposes.

    IMPORTANT: this is NOT the real encryption key -- Fernet keys must stay
    random-looking base64, so readable names can't be baked into the actual
    key material. This is purely a decorative wrapper around a short hash
    fingerprint of the real key, so it looks personalized but reveals
    nothing usable to someone who doesn't already have the real key.
    """
    fingerprint = hashlib.sha256(real_key.encode('utf-8')).digest()
    b64_fp = base64.urlsafe_b64encode(fingerprint).decode('utf-8')

    prefix = b64_fp[:8]
    middle_symbols = "(@"
    suffix = b64_fp[8:12]

    return f"{prefix}{creator.strip().upper()}{middle_symbols}{friend.strip().upper()}{suffix}="


def key_from_display_inputs(creator: str, friend: str) -> dict:
    """
    Convenience wrapper: give it the two names, get back both the real
    working key and the cosmetic display version in one call.
    """
    real = key_from_names(creator, friend)
    shown = display_key(creator, friend, real)
    return {"real_key": real, "display_key": shown}


def create_dual_qr(public_url: str, secret_msg: str, key_str: str, output_path: str = "dual_qr.png") -> str:
    """
    Encrypts secret_msg with key_str, embeds it in public_url query param,
    and generates the QR code image.
    """
    f = Fernet(key_str.encode('utf-8'))

    # Encrypt secret message (supports any language/UTF-8 character)
    encrypted_bytes = f.encrypt(secret_msg.encode('utf-8'))
    encoded_param = urllib.parse.quote(encrypted_bytes.decode('utf-8'))

    # Build URL payload
    separator = "&" if "?" in public_url else "?"
    full_payload = f"{public_url}{separator}d={encoded_param}"

    # Generate QR Code
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(full_payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    return output_path


def scan_qr_image(image_path: str) -> str:
    """
    Reads a QR code image from disk and returns the raw decoded string,
    exactly as a phone camera or scanner app would see it.
    """
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")

    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)

    if not data:
        raise ValueError("No QR code detected in image, or it could not be decoded.")

    return data


def scan_qr_from_camera(camera_index: int = 0, timeout_seconds: int = 30) -> str:
    """
    Opens your webcam, shows a live preview, and returns the raw decoded
    string as soon as a QR code is recognized in frame.

    Press 'q' at any time to cancel the scan.
    Requires a local webcam -- this will not work on a headless server.
    """
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError(
            "Could not access the camera. Make sure a webcam is connected "
            "and not being used by another app, and that this program has "
            "camera permission."
        )

    detector = cv2.QRCodeDetector()
    start_time = time.time()
    decoded_data = None

    print("📷 Point your camera at the QR code... (press 'q' to cancel)")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            data, points, _ = detector.detectAndDecode(frame)

            # Draw a box around the QR code once it's found, for visual feedback
            if points is not None and len(points) > 0:
                pts = points[0].astype(int)
                for i in range(len(pts)):
                    cv2.line(frame, tuple(pts[i]), tuple(pts[(i + 1) % len(pts)]), (0, 255, 0), 2)

            cv2.imshow("Scan QR Code - press 'q' to cancel", frame)

            if data:
                decoded_data = data
                break

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            if time.time() - start_time > timeout_seconds:
                print("⏱️  Timed out waiting for a QR code.")
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

    if not decoded_data:
        raise ValueError("No QR code was scanned (cancelled or timed out).")

    return decoded_data


def decrypt_qr_data(raw_qr_data: str, key_str: str) -> dict:
    """
    Extracts the clean public URL and decrypts the hidden secret message
    from any scanned QR string.
    """
    f = Fernet(key_str.encode('utf-8'))

    # Normal Scanner View: Clean Public URL
    clean_public_url = raw_qr_data.split('?d=')[0].split('&d=')[0]
    secret_msg = None

    # Secret Scanner View: Decrypt ?d= parameter
    if "d=" in raw_qr_data:
        try:
            parsed_url = urllib.parse.urlparse(raw_qr_data)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            encrypted_val = query_params.get('d', [None])[0]

            if encrypted_val:
                raw_encrypted_bytes = urllib.parse.unquote(encrypted_val).encode('utf-8')
                secret_msg = f.decrypt(raw_encrypted_bytes).decode('utf-8')
        except Exception as e:
            secret_msg = f"Decryption Failed: {str(e)}"

    return {
        "public": clean_public_url,
        "secret": secret_msg
    }



# ======================================================================
# UI — everything below is presentation only, no logic changes above
# ======================================================================

# "Case file" theme — aged paper + stamp-red ink, instead of a dark
# purple-gradient look. Every widget below is built purely off these
# constants, so this block is the only place colors/fonts are chosen.
BG = "#ece3cf"
BG_GRADIENT_TOP = "#ece3cf"
PANEL = "#f7f1e2"
PANEL_ALT = "#e3d7b8"
PANEL_SOFT = "#efe6d2"
ACCENT = "#97302f"
ACCENT_HOVER = "#ab3d3a"
ACCENT_DIM = "#c9bc9c"
ACCENT_2 = "#2f5f42"
ACCENT_2_DIM = "#3f6b4c"
TEXT = "#241f18"
SUBTEXT = "#6b6250"
MUTED = "#948a72"
ENTRY_BG = "#fffdf7"
ENTRY_BG_FOCUS = "#fff8e8"
BORDER = "#c7b992"
BORDER_FOCUS = "#97302f"
DANGER = "#97302f"
GOLD = "#a97c3f"
BTN_TEXT = "#fbf3e4"        # light ink used on top of the dark-red accent
BTN_DISABLED = "#b7ab8c"    # muted paper-grey for disabled buttons

FONT_TITLE = ("Georgia", 22, "bold")
FONT_SUB = ("Georgia", 10)
FONT_LABEL = ("Consolas", 9, "bold")
FONT_HINT = ("Georgia", 8, "italic")
FONT_BODY = ("Georgia", 10)
FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 9)
FONT_BTN = ("Courier New", 10, "bold")
FONT_CARD_TITLE = ("Courier New", 12, "bold")
FONT_STEP_NUM = ("Georgia", 13, "bold")


def _round_rect_points(x1, y1, x2, y2, r):
    r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
    return [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]


class RoundedButton(tk.Canvas):
    """A small canvas-based button with rounded corners, hover + disabled state."""

    def __init__(self, parent, text, command, bg=ACCENT, hover=ACCENT_HOVER,
                 fg=BTN_TEXT, width=180, height=38, font=FONT_BTN, icon="", **kw):
        super().__init__(parent, width=width, height=height, bg=parent["bg"],
                          highlightthickness=0, **kw)
        self.command = command
        self.bg_color = bg
        self.hover_color = hover
        self.fg_color = fg
        self.width, self.height = width, height
        self.font = font
        self.text = text
        self.enabled = True
        self._draw(bg)
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self.enabled and self._draw(self.hover_color))
        self.bind("<Leave>", lambda e: self.enabled and self._draw(self.bg_color))
        self.configure(cursor="hand2")

    def _draw(self, color):
        self.delete("all")
        self.create_polygon(_round_rect_points(1, 1, self.width - 1, self.height - 1, 12),
                             smooth=True, fill=color, outline="")
        self.create_text(self.width / 2, self.height / 2, text=self.text,
                          fill=self.fg_color, font=self.font)

    def _click(self, event):
        if self.command and self.enabled:
            self.command()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw(self.bg_color if enabled else BTN_DISABLED)


class GhostButton(tk.Canvas):
    """Small outlined/secondary button — used for Copy, Browse-style actions."""

    def __init__(self, parent, text, command, width=88, height=28,
                 fg=SUBTEXT, hover_fg=TEXT, font=("Segoe UI", 9), **kw):
        super().__init__(parent, width=width, height=height, bg=parent["bg"],
                          highlightthickness=0, **kw)
        self.command = command
        self.text = text
        self.fg = fg
        self.hover_fg = hover_fg
        self.font = font
        self.width, self.height = width, height
        self._draw(BORDER, fg)
        self.bind("<Button-1>", lambda e: self.command and self.command())
        self.bind("<Enter>", lambda e: self._draw(ACCENT, self.hover_fg))
        self.bind("<Leave>", lambda e: self._draw(BORDER, self.fg))
        self.configure(cursor="hand2")

    def _draw(self, border, textcolor):
        self.delete("all")
        self.create_polygon(_round_rect_points(1, 1, self.width - 1, self.height - 1, 8),
                             smooth=True, fill="", outline=border, width=1)
        self.create_text(self.width / 2, self.height / 2, text=self.text,
                          fill=textcolor, font=self.font)

    def flash(self, temp_text):
        old = self.text
        self.text = temp_text
        self._draw(ACCENT_2, ACCENT_2)
        self.after(900, lambda: (setattr(self, "text", old), self._draw(BORDER, self.fg)))


class StatusPill(tk.Frame):
    """Small colored-dot + text status indicator."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=parent["bg"], **kw)
        self.dot = tk.Canvas(self, width=10, height=10, bg=parent["bg"], highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 8))
        self.label = tk.Label(self, text="", bg=parent["bg"], fg=SUBTEXT,
                               font=FONT_SUB, wraplength=520, justify="left", anchor="w")
        self.label.pack(side="left", fill="x")
        self._set_dot(MUTED)

    def _set_dot(self, color):
        self.dot.delete("all")
        self.dot.create_oval(1, 1, 9, 9, fill=color, outline="")

    def set(self, text, kind="idle"):
        colors = {"idle": MUTED, "info": SUBTEXT, "success": ACCENT_2,
                  "error": DANGER, "working": GOLD}
        color = colors.get(kind, MUTED)
        self._set_dot(color)
        self.label.configure(text=text, fg=(TEXT if kind != "idle" else SUBTEXT))


def styled_entry(parent, show=None, mono=False):
    e = tk.Entry(parent, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=(FONT_MONO if mono else FONT_BODY),
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=BORDER_FOCUS, show=show)
    e.bind("<FocusIn>", lambda ev: e.configure(bg=ENTRY_BG_FOCUS))
    e.bind("<FocusOut>", lambda ev: e.configure(bg=ENTRY_BG))
    return e


def styled_text(parent, height=4, mono=False, fg=TEXT, disabled_fg=None):
    """A Text widget that stays readable even when disabled. Tk's Text
    widget has no `disabledforeground` option (unlike Entry) — the plain
    `fg` color is what stays visible in disabled state, so that's all we
    set here."""
    t = tk.Text(parent, height=height, bg=ENTRY_BG, fg=fg, relief="flat",
                font=(FONT_MONO if mono else FONT_BODY), insertbackground=TEXT,
                highlightthickness=1, highlightbackground=BORDER,
                highlightcolor=BORDER_FOCUS, wrap="word", padx=10, pady=8)
    t.bind("<FocusIn>", lambda ev: t.configure(bg=ENTRY_BG_FOCUS) if str(t["state"]) == "normal" else None)
    t.bind("<FocusOut>", lambda ev: t.configure(bg=ENTRY_BG))
    return t


def icon_label(parent, icon, text, sub=None):
    row = tk.Frame(parent, bg=parent["bg"])
    tk.Label(row, text=icon, bg=parent["bg"], fg=ACCENT, font=("Segoe UI", 13)).pack(side="left", padx=(0, 8))
    col = tk.Frame(row, bg=parent["bg"])
    col.pack(side="left")
    tk.Label(col, text=text, bg=parent["bg"], fg=TEXT, font=FONT_CARD_TITLE, anchor="w").pack(anchor="w")
    if sub:
        tk.Label(col, text=sub, bg=parent["bg"], fg=MUTED, font=FONT_HINT, anchor="w").pack(anchor="w")
    return row


def section_label(parent, text, hint=None):
    col = tk.Frame(parent, bg=parent["bg"])
    tk.Label(col, text=text.upper(), bg=parent["bg"], fg=SUBTEXT, font=FONT_LABEL).pack(anchor="w")
    if hint:
        tk.Label(col, text=hint, bg=parent["bg"], fg=MUTED, font=FONT_HINT).pack(anchor="w")
    return col


def card(parent, **kw):
    f = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER,
                 highlightthickness=1, **kw)
    return f


def step_badge(parent, number):
    c = tk.Canvas(parent, width=26, height=26, bg=parent["bg"], highlightthickness=0)
    c.create_oval(1, 1, 25, 25, fill=PANEL_SOFT, outline=ACCENT_DIM)
    c.create_text(13, 13, text=str(number), fill=ACCENT_2, font=FONT_STEP_NUM)
    return c


class DualQRApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dual-Message QR Tool")
        self.geometry("1160x760")
        self.minsize(1000, 660)
        self.configure(bg=BG)
        try:
            self.iconphoto(False, tk.PhotoImage(width=1, height=1))
        except Exception:
            pass

        self._build_header()
        self._build_tabs()
        self._build_footer()

    # ------------------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=32, pady=(24, 4))

        top = tk.Frame(header, bg=BG)
        top.pack(fill="x")

        logo = tk.Canvas(top, width=48, height=48, bg=BG, highlightthickness=0)
        logo.create_polygon(_round_rect_points(0, 0, 48, 48, 14), smooth=True, fill=PANEL_SOFT, outline=ACCENT_DIM)
        logo.create_text(24, 24, text="▦", fill=ACCENT_2, font=("Segoe UI", 20))
        logo.pack(side="left", padx=(0, 14))

        title_col = tk.Frame(top, bg=BG)
        title_col.pack(side="left")
        tk.Label(title_col, text="Dual-Message QR Tool", bg=BG, fg=TEXT,
                 font=FONT_TITLE).pack(anchor="w")
        tk.Label(title_col,
                 text="One QR code, two messages — a public message everyone sees, and a secret only your key unlocks.",
                 bg=BG, fg=SUBTEXT, font=FONT_SUB).pack(anchor="w", pady=(2, 0))

        badge = tk.Frame(top, bg=PANEL_SOFT, highlightbackground=ACCENT_DIM, highlightthickness=1)
        badge.pack(side="right", pady=4)
        tk.Label(badge, text="🔒 AES-256 · Fernet encrypted", bg=PANEL_SOFT, fg=ACCENT_2,
                 font=("Segoe UI", 9)).pack(padx=12, pady=6)

    def _build_footer(self):
        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", padx=32, pady=(0, 14))
        tk.Label(foot,
                 text="Tip: two plain names is a fun-level secret, not a strong one. For real privacy, "
                      "agree on a shared suffix only you two know (e.g. \"vishal-blue42\").",
                 bg=BG, fg=MUTED, font=FONT_HINT).pack(anchor="w")

    def _build_tabs(self):
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=SUBTEXT,
                         padding=(22, 12), font=FONT_LABEL, borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BTN_TEXT)])
        style.layout("TNotebook.Tab", [
            ('Notebook.tab', {'sticky': 'nswe', 'children':
                [('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children':
                    [('Notebook.label', {'side': 'top', 'sticky': ''})]})]})
        ])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=32, pady=(8, 0))

        create_tab = tk.Frame(nb, bg=BG)
        decrypt_tab = tk.Frame(nb, bg=BG)
        about_tab = tk.Frame(nb, bg=BG)
        nb.add(create_tab, text="  ✨  Create QR  ")
        nb.add(decrypt_tab, text="  🔍  Decrypt QR  ")
        nb.add(about_tab, text="  ℹ️  How it works  ")

        self._build_create_tab(create_tab)
        self._build_decrypt_tab(decrypt_tab)
        self._build_about_tab(about_tab)

    # ------------------------------------------------------------------
    # CREATE TAB
    # ------------------------------------------------------------------
    def _build_create_tab(self, parent):
        canvas_wrap, wrap = self._scrollable(parent)
        wrap.columnconfigure(0, weight=3)
        wrap.columnconfigure(1, weight=2)

        # left: form card
        left = card(wrap)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=16)
        left.columnconfigure(0, weight=1)

        header = tk.Frame(left, bg=PANEL)
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(20, 6))
        icon_label(header, "✨", "Message details", "Fill these in, then generate your QR").pack(anchor="w")

        pad = {"padx": 22, "pady": (14, 4)}

        section_label(left, "Your name (creator)").grid(row=1, column=0, sticky="w", **pad)
        self.c_creator = styled_entry(left)
        self.c_creator.grid(row=2, column=0, sticky="ew", padx=22, ipady=7)

        section_label(left, "Friend's name").grid(row=3, column=0, sticky="w", **pad)
        self.c_friend = styled_entry(left)
        self.c_friend.grid(row=4, column=0, sticky="ew", padx=22, ipady=7)

        section_label(left, "Public message", "What a normal scan shows — a link, a note, anything").grid(row=5, column=0, sticky="w", **pad)
        self.c_public_url = styled_entry(left)
        self.c_public_url.grid(row=6, column=0, sticky="ew", padx=22, ipady=7)

        section_label(left, "Secret message", "Hidden inside the QR, any language").grid(row=7, column=0, sticky="w", **pad)
        self.c_secret = styled_text(left, height=4)
        self.c_secret.grid(row=8, column=0, sticky="ew", padx=22)

        section_label(left, "Output filename").grid(row=9, column=0, sticky="w", **pad)
        out_row = tk.Frame(left, bg=PANEL)
        out_row.grid(row=10, column=0, sticky="ew", padx=22)
        out_row.columnconfigure(0, weight=1)
        self.c_output = styled_entry(out_row)
        self.c_output.insert(0, "dual_qr.png")
        self.c_output.grid(row=0, column=0, sticky="ew", ipady=7)
        GhostButton(out_row, "📁 Browse", self._browse_save, width=90).grid(row=0, column=1, padx=(8, 0))

        btn_row = tk.Frame(left, bg=PANEL)
        btn_row.grid(row=11, column=0, sticky="w", padx=22, pady=(22, 8))
        self.c_generate_btn = RoundedButton(btn_row, "⚡  Generate QR Code",
                                             self._on_generate, width=220)
        self.c_generate_btn.pack(side="left")

        self.c_status = StatusPill(left)
        self.c_status.grid(row=12, column=0, sticky="ew", padx=22, pady=(2, 20))

        # right: preview + keys card
        right = tk.Frame(wrap, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", pady=16)
        right.columnconfigure(0, weight=1)

        preview_card = card(right)
        preview_card.pack(fill="x", pady=(0, 14))
        preview_card.columnconfigure(0, weight=1)

        icon_label(preview_card, "🖼", "QR preview").grid(row=0, column=0, sticky="w", padx=20, pady=(18, 10))

        self.qr_preview_frame = tk.Frame(preview_card, bg=PANEL_ALT, width=280, height=280,
                                          highlightbackground=BORDER, highlightthickness=1)
        self.qr_preview_frame.grid(row=1, column=0, padx=20, pady=(0, 10))
        self.qr_preview_frame.grid_propagate(False)
        self.qr_preview_label = tk.Label(self.qr_preview_frame, bg=PANEL_ALT,
                                          text="🔳\nYour QR will appear here",
                                          fg=MUTED, font=FONT_SUB, justify="center")
        self.qr_preview_label.place(relx=0.5, rely=0.5, anchor="center")

        self.c_saved_path = tk.Label(preview_card, text="", bg=PANEL, fg=MUTED,
                                      font=FONT_HINT, wraplength=280, justify="center")
        self.c_saved_path.grid(row=2, column=0, pady=(0, 18))

        keys_card = card(right)
        keys_card.pack(fill="x")
        keys_card.columnconfigure(0, weight=1)

        icon_label(keys_card, "🔑", "Keys", "Keep the real key safe — it decrypts the secret").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 10))

        section_label(keys_card, "Display key", "Fun cosmetic version, safe to show off").grid(
            row=1, column=0, sticky="w", padx=20)
        dk_row = tk.Frame(keys_card, bg=PANEL)
        dk_row.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 12))
        dk_row.columnconfigure(0, weight=1)
        self.c_display_key = self._readonly_field(dk_row, fg=GOLD)
        self.c_display_key.grid(row=0, column=0, sticky="ew", ipady=6)
        self.c_display_copy = GhostButton(dk_row, "Copy", lambda: self._copy(self.c_display_key, self.c_display_copy), width=64)
        self.c_display_copy.grid(row=0, column=1, padx=(8, 0))

        section_label(keys_card, "Real key", "Required to decrypt — store it somewhere safe").grid(
            row=3, column=0, sticky="w", padx=20)
        rk_row = tk.Frame(keys_card, bg=PANEL)
        rk_row.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 20))
        rk_row.columnconfigure(0, weight=1)
        self.c_real_key = self._readonly_field(rk_row, fg=ACCENT_2)
        self.c_real_key.grid(row=0, column=0, sticky="ew", ipady=6)
        self.c_real_copy = GhostButton(rk_row, "Copy", lambda: self._copy(self.c_real_key, self.c_real_copy), width=64)
        self.c_real_copy.grid(row=0, column=1, padx=(8, 0))

    def _readonly_field(self, parent, fg=TEXT):
        e = tk.Entry(parent, bg=ENTRY_BG, fg=fg, relief="flat", font=FONT_MONO_SM,
                     highlightthickness=1, highlightbackground=BORDER, state="readonly",
                     readonlybackground=ENTRY_BG, disabledforeground=fg)
        return e

    def _set_readonly(self, entry, value):
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value)
        entry.configure(state="readonly")

    def _copy(self, entry, button):
        value = entry.get()
        if not value:
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        button.flash("Copied!")

    def _browse_save(self):
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                             filetypes=[("PNG image", "*.png")],
                                             initialfile="dual_qr.png")
        if path:
            self.c_output.delete(0, "end")
            self.c_output.insert(0, path)

    def _on_generate(self):
        creator = self.c_creator.get().strip()
        friend = self.c_friend.get().strip()
        public_url = self.c_public_url.get().strip()
        secret = self.c_secret.get("1.0", "end").strip()
        output_path = self.c_output.get().strip() or "dual_qr.png"

        if not all([creator, friend, public_url, secret]):
            self.c_status.set("⚠️  All fields are required.", "error")
            return

        self.c_status.set("Generating…", "working")
        self.c_generate_btn.set_enabled(False)
        self.update_idletasks()

        try:
            keys = key_from_display_inputs(creator, friend)
            real_key = keys["real_key"]
            create_dual_qr(public_url, secret, real_key, output_path)
        except Exception as e:
            self.c_status.set(f"❌ {e}", "error")
            self.c_generate_btn.set_enabled(True)
            return

        self._set_readonly(self.c_display_key, keys["display_key"])
        self._set_readonly(self.c_real_key, real_key)
        self._show_preview(output_path)
        self.c_saved_path.configure(text=f"Saved to: {os.path.abspath(output_path)}")
        self.c_status.set("QR generated. Save the real key — you and your friend both need it to decrypt.", "success")
        self.c_generate_btn.set_enabled(True)

    def _show_preview(self, image_path):
        try:
            img = Image.open(image_path)
            img.thumbnail((256, 256))
            photo = ImageTk.PhotoImage(img)
            self.qr_preview_label.configure(image=photo, text="")
            self.qr_preview_label.image = photo  # keep reference
        except Exception:
            self.qr_preview_label.configure(text="⚠️\nPreview unavailable", image="")

    # ------------------------------------------------------------------
    # DECRYPT TAB
    # ------------------------------------------------------------------
    def _build_decrypt_tab(self, parent):
        canvas_wrap, wrap = self._scrollable(parent)
        wrap.columnconfigure(0, weight=3)
        wrap.columnconfigure(1, weight=2)

        left = tk.Frame(wrap, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=16)
        left.columnconfigure(0, weight=1)

        card1 = card(left)
        card1.pack(fill="x", pady=(0, 14))
        card1.columnconfigure(0, weight=1)

        icon_label(card1, "🔑", "Step 1 — Key").grid(row=0, column=0, sticky="w", padx=20, pady=(18, 10))
        self.d_key_mode = tk.StringVar(value="real")
        mode_row = tk.Frame(card1, bg=PANEL)
        mode_row.grid(row=1, column=0, sticky="w", padx=20)
        tk.Radiobutton(mode_row, text="I have the real key", variable=self.d_key_mode,
                       value="real", command=self._toggle_key_mode, bg=PANEL, fg=TEXT,
                       selectcolor=PANEL_ALT, activebackground=PANEL, activeforeground=TEXT,
                       font=FONT_BODY, highlightthickness=0, cursor="hand2").pack(side="left", padx=(0, 20))
        tk.Radiobutton(mode_row, text="Derive from both names", variable=self.d_key_mode,
                       value="names", command=self._toggle_key_mode, bg=PANEL, fg=TEXT,
                       selectcolor=PANEL_ALT, activebackground=PANEL, activeforeground=TEXT,
                       font=FONT_BODY, highlightthickness=0, cursor="hand2").pack(side="left")

        self.d_key_stack = tk.Frame(card1, bg=PANEL)
        self.d_key_stack.grid(row=2, column=0, sticky="ew", padx=20, pady=(12, 20))
        self.d_key_stack.columnconfigure(0, weight=1)

        self.d_real_frame = tk.Frame(self.d_key_stack, bg=PANEL)
        self.d_real_frame.grid(row=0, column=0, sticky="ew")
        self.d_real_frame.columnconfigure(0, weight=1)
        self.d_key_input = styled_entry(self.d_real_frame, mono=True)
        self.d_key_input.grid(row=0, column=0, sticky="ew", ipady=7)

        self.d_names_frame = tk.Frame(self.d_key_stack, bg=PANEL)
        self.d_names_frame.columnconfigure(0, weight=1)
        self.d_names_frame.columnconfigure(1, weight=1)
        tk.Label(self.d_names_frame, text="Creator name", bg=PANEL, fg=MUTED,
                 font=FONT_HINT).grid(row=0, column=0, sticky="w")
        tk.Label(self.d_names_frame, text="Friend name", bg=PANEL, fg=MUTED,
                 font=FONT_HINT).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.d_creator_name = styled_entry(self.d_names_frame)
        self.d_friend_name = styled_entry(self.d_names_frame)
        self.d_creator_name.grid(row=1, column=0, sticky="ew", ipady=7)
        self.d_friend_name.grid(row=1, column=1, sticky="ew", ipady=7, padx=(10, 0))

        card2 = card(left)
        card2.pack(fill="x", pady=(0, 14))
        card2.columnconfigure(0, weight=1)

        icon_label(card2, "📷", "Step 2 — QR source", "Pick a saved image or scan live").grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 10))
        img_row = tk.Frame(card2, bg=PANEL)
        img_row.grid(row=1, column=0, sticky="ew", padx=20)
        img_row.columnconfigure(0, weight=1)
        self.d_image_path = styled_entry(img_row)
        self.d_image_path.grid(row=0, column=0, sticky="ew", ipady=7)
        GhostButton(img_row, "📁 Browse", self._browse_open, width=90).grid(row=0, column=1, padx=(8, 8))
        GhostButton(img_row, "📷 Camera", self._on_camera_scan, width=90).grid(row=0, column=2)

        self.d_thumb_frame = tk.Frame(card2, bg=PANEL_ALT, width=120, height=120,
                                       highlightbackground=BORDER, highlightthickness=1)
        self.d_thumb_frame.grid(row=2, column=0, sticky="w", padx=20, pady=16)
        self.d_thumb_frame.grid_propagate(False)
        self.d_thumb_label = tk.Label(self.d_thumb_frame, bg=PANEL_ALT, text="No image\nyet",
                                       fg=MUTED, font=FONT_HINT, justify="center")
        self.d_thumb_label.place(relx=0.5, rely=0.5, anchor="center")

        btn_row = tk.Frame(left, bg=BG)
        btn_row.pack(fill="x", pady=(0, 4))
        self.d_decrypt_btn = RoundedButton(btn_row, "🔓  Decrypt", self._on_decrypt, width=170)
        self.d_decrypt_btn.pack(side="left")

        self.d_status = StatusPill(btn_row)
        self.d_status.pack(side="left", padx=16, fill="x", expand=True)

        # right: results card
        right = card(wrap)
        right.grid(row=0, column=1, sticky="nsew", pady=16)
        right.columnconfigure(0, weight=1)

        icon_label(right, "📬", "Results").grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        section_label(right, "Raw scanned data").grid(row=1, column=0, sticky="w", padx=20)
        self.d_raw = styled_text(right, height=3, mono=True, fg=SUBTEXT, disabled_fg=SUBTEXT)
        self.d_raw.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 16))

        section_label(right, "🌐  Public message", "Visible to anyone who scans it").grid(
            row=3, column=0, sticky="w", padx=20)
        pub_row = tk.Frame(right, bg=PANEL)
        pub_row.grid(row=4, column=0, sticky="ew", padx=20, pady=(4, 16))
        pub_row.columnconfigure(0, weight=1)
        self.d_public_out = self._readonly_field(pub_row, fg=TEXT)
        self.d_public_out.grid(row=0, column=0, sticky="ew", ipady=6)

        section_label(right, "🔐  Secret message", "Only visible with the correct key").grid(
            row=5, column=0, sticky="w", padx=20)
        secret_card = tk.Frame(right, bg=PANEL_SOFT, highlightbackground=ACCENT_DIM, highlightthickness=1)
        secret_card.grid(row=6, column=0, sticky="ew", padx=20, pady=(4, 20))
        secret_card.columnconfigure(0, weight=1)
        self.d_secret_out = tk.Text(secret_card, height=5, bg=PANEL_SOFT, fg=ACCENT_2,
                                     relief="flat", font=("Segoe UI", 11), wrap="word",
                                     padx=12, pady=10, highlightthickness=0,
                                     state="disabled")
        self.d_secret_out.grid(row=0, column=0, sticky="ew")
        self._set_text(self.d_secret_out, "Decrypt a QR code to reveal its hidden message here.", disabled=True, fg=MUTED)

        self._toggle_key_mode()

    def _toggle_key_mode(self):
        if self.d_key_mode.get() == "real":
            self.d_names_frame.grid_forget()
            self.d_real_frame.grid(row=0, column=0, sticky="ew")
        else:
            self.d_real_frame.grid_forget()
            self.d_names_frame.grid(row=0, column=0, sticky="ew")

    def _browse_open(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp"), ("All files", "*.*")])
        if path:
            self.d_image_path.delete(0, "end")
            self.d_image_path.insert(0, path)
            self._show_thumb(path)

    def _show_thumb(self, image_path):
        try:
            img = Image.open(image_path)
            img.thumbnail((110, 110))
            photo = ImageTk.PhotoImage(img)
            self.d_thumb_label.configure(image=photo, text="")
            self.d_thumb_label.image = photo
        except Exception:
            self.d_thumb_label.configure(text="Preview\nunavailable", image="")

    def _resolve_key(self):
        if self.d_key_mode.get() == "real":
            key = self.d_key_input.get().strip()
            if not key:
                raise ValueError("Please paste the real key.")
            return key
        else:
            creator = self.d_creator_name.get().strip()
            friend = self.d_friend_name.get().strip()
            if not creator or not friend:
                raise ValueError("Please enter both names.")
            return key_from_names(creator, friend)

    def _on_camera_scan(self):
        # Runs the original blocking OpenCV window in a background thread
        # so the Tkinter UI doesn't freeze while the camera preview is open.
        self.d_status.set("Opening camera… press 'q' in that window to cancel.", "working")
        self.d_decrypt_btn.set_enabled(False)

        def worker():
            try:
                scanned = scan_qr_from_camera()
                self.after(0, lambda: self._on_scanned(scanned))
            except Exception as e:
                self.after(0, lambda: self.d_status.set(f"❌ {e}", "error"))
            finally:
                self.after(0, lambda: self.d_decrypt_btn.set_enabled(True))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scanned(self, scanned_string):
        self.d_status.set("Camera scan captured. Click Decrypt.", "success")
        self._set_text(self.d_raw, scanned_string, disabled=True, fg=SUBTEXT)
        self.d_image_path.delete(0, "end")
        self.d_thumb_label.configure(text="📷\nfrom camera", image="")

    def _set_text(self, widget, value, disabled=False, fg=None):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value or "")
        if fg:
            widget.configure(fg=fg)
        if disabled:
            widget.configure(state="disabled")

    def _on_decrypt(self):
        try:
            key = self._resolve_key()
        except ValueError as e:
            self.d_status.set(f"⚠️ {e}", "error")
            return

        raw_current = self.d_raw.get("1.0", "end").strip()
        image_path = self.d_image_path.get().strip()

        try:
            if image_path:
                scanned = scan_qr_image(image_path)
                self._set_text(self.d_raw, scanned, disabled=True, fg=SUBTEXT)
            elif raw_current:
                scanned = raw_current
            else:
                raise ValueError("Pick an image file or run a live camera scan first.")
        except (FileNotFoundError, ValueError) as e:
            self.d_status.set(f"❌ {e}", "error")
            return

        result = decrypt_qr_data(scanned, key)
        self._set_readonly(self.d_public_out, result["public"])

        secret = result["secret"]
        if secret and not str(secret).startswith("Decryption Failed"):
            self._set_text(self.d_secret_out, secret, disabled=True, fg=ACCENT_2)
            self.d_status.set("Secret unlocked successfully.", "success")
        else:
            self._set_text(self.d_secret_out, secret or "(no secret parameter found in this QR)",
                            disabled=True, fg=DANGER)
            self.d_status.set("No valid secret with this key — check the key or names.", "error")

    # ------------------------------------------------------------------
    # ABOUT TAB
    # ------------------------------------------------------------------
    def _build_about_tab(self, parent):
        canvas_wrap, wrap = self._scrollable(parent)
        wrap.columnconfigure(0, weight=1)

        intro = card(wrap)
        intro.pack(fill="x", pady=16)
        icon_label(intro, "🧩", "What this tool does").pack(anchor="w", padx=22, pady=(18, 8))
        tk.Label(intro, justify="left", wraplength=880, bg=PANEL, fg=SUBTEXT, font=FONT_BODY,
                 text=("A single QR code that behaves two ways: scanned normally by anyone, "
                       "it just shows your public message (a link, a note, whatever you put in). "
                       "Scanned or decrypted here with the right key, it also reveals a hidden "
                       "message encrypted alongside it.")).pack(anchor="w", padx=22, pady=(0, 20))

        steps = card(wrap)
        steps.pack(fill="x", pady=(0, 16))
        icon_label(steps, "🛠", "How it works").pack(anchor="w", padx=22, pady=(18, 14))

        step_defs = [
            ("Pick two names", "You and your friend's names are combined (order doesn't matter) and "
                                "run through PBKDF2-HMAC-SHA256 (390,000 iterations) to derive a real, "
                                "random-looking Fernet key."),
            ("Encrypt the secret", "Your hidden message is encrypted with that key using Fernet "
                                    "(AES-128-CBC + HMAC), then URL-safely attached after your public "
                                    "message as a `?d=` (or `&d=`) parameter."),
            ("Generate the QR", "Your public message plus the encrypted payload become the QR code "
                                 "image. A normal scan just shows your public text with a bit of extra "
                                 "data tacked on the end — harmless if it's a link, and still readable "
                                 "if it's plain text."),
            ("Decrypt later", "Anyone with the real key (or just both names) can paste/scan the code "
                               "back here and reveal the original secret message."),
        ]
        for i, (title, desc) in enumerate(step_defs):
            row = tk.Frame(steps, bg=PANEL)
            row.pack(fill="x", padx=22, pady=(0, 16 if i < len(step_defs) - 1 else 20))
            step_badge(row, i + 1).pack(side="left", padx=(0, 14), anchor="n")
            col = tk.Frame(row, bg=PANEL)
            col.pack(side="left", fill="x", expand=True)
            tk.Label(col, text=title, bg=PANEL, fg=TEXT, font=FONT_LABEL, anchor="w").pack(anchor="w")
            tk.Label(col, text=desc, bg=PANEL, fg=SUBTEXT, font=FONT_BODY, anchor="w",
                     justify="left", wraplength=780).pack(anchor="w", pady=(2, 0))

        note = card(wrap)
        note.pack(fill="x", pady=(0, 24))
        icon_label(note, "⚠️", "Security note").pack(anchor="w", padx=22, pady=(18, 8))
        tk.Label(note, justify="left", wraplength=880, bg=PANEL, fg=SUBTEXT, font=FONT_BODY,
                 text=("Two plain names alone is a guessable secret if someone knows you two "
                       "exchange QR codes — fine for casual/fun use. For anything more sensitive, "
                       "agree on a shared suffix only the two of you know, or generate and share a "
                       "fully random key instead.")).pack(anchor="w", padx=22, pady=(0, 20))

    # ------------------------------------------------------------------
    def _scrollable(self, parent):
        """Wraps a tab's content in a vertically scrollable canvas."""
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        inner = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=inner, anchor="nw")

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_resize(event):
            canvas.itemconfig(window, width=event.width)

        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", on_canvas_resize)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

        return canvas, inner


def main():
    app = DualQRApp()
    app.mainloop()


if __name__ == "__main__":
    main()