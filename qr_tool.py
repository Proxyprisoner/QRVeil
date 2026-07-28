import base64
import hashlib
import urllib.parse
import qrcode
import cv2
from cryptography.fernet import Fernet


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


def _print_header(text: str):
    print("\n" + "=" * 55)
    print(f" {text}")
    print("=" * 55)


def _run_create_flow():
    _print_header("CREATE A DUAL-MESSAGE QR CODE")

    creator_name = input("Your name (creator): ").strip()
    friend_name = input("Friend's name: ").strip()
    public_link = input("Public URL (what a normal scan should show): ").strip()
    secret_text = input("Secret message to hide: ").strip()
    default_path = f"dual_qr_{friend_name.lower() or 'friend'}.png"
    output_path = input(f"Output filename [{default_path}]: ").strip() or default_path

    if not all([creator_name, friend_name, public_link, secret_text]):
        print("\n⚠️  All fields are required. Please try again.")
        return

    keys = key_from_display_inputs(creator_name, friend_name)
    real_key = keys["real_key"]

    create_dual_qr(public_link, secret_text, real_key, output_path)

    print("\n✅ QR code created successfully!")
    print(f"   File saved as:   {output_path}")
    print(f"   Display key:     {keys['display_key']}   (just for show)")
    print(f"   Real key:        {real_key}")
    print("\n📌 Save the REAL key somewhere safe -- you and your friend")
    print("   both need it (or both names, in any order) to decrypt later.")


def _run_decrypt_flow():
    _print_header("DECRYPT A QR CODE")

    print("How do you want to provide the key?")
    print("  1) I have the real key")
    print("  2) I know both names (creator + friend) and want it re-derived")
    choice = input("Choose 1 or 2: ").strip()

    if choice == "2":
        creator_name = input("Creator's name: ").strip()
        friend_name = input("Friend's name: ").strip()
        real_key = key_from_names(creator_name, friend_name)
        print(f"\n🔑 Re-derived real key: {real_key}")
    else:
        real_key = input("Paste the real key: ").strip()

    image_path = input("Path to the QR image file (e.g. dual_qr_arun.png): ").strip()

    try:
        scanned_string = scan_qr_image(image_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ Couldn't read that QR code: {e}")
        return

    result = decrypt_qr_data(scanned_string, real_key)

    print("\n📷 Raw scanned data:")
    print(f"   {scanned_string}")
    print(f"\n🌐 Public URL (visible to anyone): {result['public']}")
    if result["secret"] and not str(result["secret"]).startswith("Decryption Failed"):
        print(f"🔐 Secret message unlocked:        {result['secret']}")
    else:
        print(f"🔐 Secret message:                 {result['secret'] or '(none found)'}")


def main():
    while True:
        _print_header("DUAL-MESSAGE QR TOOL")
        print("1) Create a new QR code (encode a hidden message)")
        print("2) Decrypt an existing QR code")
        print("3) Quit")
        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            _run_create_flow()
        elif choice == "2":
            _run_decrypt_flow()
        elif choice == "3":
            print("\nGoodbye! 👋")
            break
        else:
            print("\n⚠️  Please enter 1, 2, or 3.")


# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    main()