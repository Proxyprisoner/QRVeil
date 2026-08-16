# Changelog

All notable changes to this project, by version tag.

`v1.0.0` is the real starting point: pure encryption/QR core logic, no UI.
The two commits before it (`v0.1.0-proto`, `v0.2.0-proto`) are early
CLI/desktop drafts kept for history but superseded by the `v1.x` line.

## [v2.0.0] — 2026-08-16
### Changed
- Flattened the project to the repo root (was nested under `dualqr_desktop/`).
- Added the project-level `README.md` and this `CHANGELOG.md`.

## [v1.5.0] — 2026-08-16
### Added
- AES-256-GCM as an alternate cipher backend alongside Fernet. Each backend
  has its own key-derivation function (Fernet keys are base64; AES-GCM keys
  are a 64-character hex string). The nonce is generated per message and
  packed in front of the ciphertext before base64-encoding.

## [v1.4.1] — 2026-08-15
### Fixed
- Removed a duplicate `vbar.pack()` call left over from the font/layout pass.

## [v1.4.0] — 2026-08-15
### Changed
- Bumped font sizes across the UI and swapped the button/heading font from
  Courier New (blocky at small sizes) to Consolas (ClearType-hinted, stays
  crisp).
- Added a real app icon/logo (envelope seal mark), used for both the
  window/taskbar icon and the in-app header mark, replacing the placeholder
  icon.
- Added a `resource_path()` helper so bundled assets resolve correctly both
  when running `app.py` directly and from a PyInstaller `--onefile` build.
- `build_exe.bat` now bundles the `assets` folder into the `.exe` and sets it
  as the executable's own file icon.

## [v1.3.1] — 2026-08-15
### Added
- MIT `LICENSE`, `.gitignore`, and four README screenshots (Create tab,
  QR generated, Decrypt result, How it works).

## [v1.3.0] — 2026-08-15
### Added
- Packaged the script as a standalone desktop project: `requirements.txt`,
  `build_exe.bat` (PyInstaller build script), and a project README covering
  running from source vs. building the `.exe`.

## [v1.2.0] — 2026-08-07
### Changed
- Rebuilt as a full Tkinter GUI ("GUI edition") on top of the same core
  logic: Create and Decrypt tabs, key generation/derivation controls, and a
  "How it works" panel. Core crypto/QR functions are unchanged from v1.0.0.

## [v1.1.0] — 2026-07-28
### Added
- Live camera QR scanning as an alternative to scanning from an image file
  (`scan_qr_from_camera`), with a live preview window and a 'q' to cancel.

## [v1.0.0] — 2026-07-28 — Starting point
### Added
- The core idea, with no UI at all: `generate_key`, `key_from_names`
  (order-independent key derivation from two names, via
  `from cryptography.fernet import Fernet`), `create_dual_qr`,
  `decrypt_qr_data`. Everything the app does today still builds on these
  four functions.

---

## Earlier drafts (pre-v1.0.0, kept for history)

## [v0.2.0-proto] — 2026-07-25
- Rewrote the first draft as a desktop app: native Tkinter video canvas for
  the camera feed, `customtkinter` UI, restartable OpenCV video-capture loop.

## [v0.1.0-proto] — 2026-07-25
- Initial prototype: three modes — public URL/text mode, personal camera
  mode (decrypts a hidden payload live from the video feed), and an LSB
  steganography file mode. Mixed CLI + Tkinter messagebox UI.
