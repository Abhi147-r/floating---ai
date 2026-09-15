"""
Optional advanced features:
  - System tray icon (minimize instead of fully closing)
  - Global hotkey to show/hide the floating window from anywhere

Both are optional: if 'pystray' or 'keyboard' aren't installed, the app
logs a note and simply skips these features instead of crashing.
"""

from __future__ import annotations
import threading

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None

try:
    import keyboard  # global hotkeys (may need admin/root on some OSes)
except Exception:
    keyboard = None


def _make_icon_image():
    img = Image.new("RGB", (64, 64), "#111318")
    d = ImageDraw.Draw(img)
    d.ellipse((10, 10, 54, 54), fill="#3d63ff")
    d.ellipse((24, 24, 40, 40), fill="#e6e6e6")
    return img


def start_tray(on_show, on_quit):
    """Run a system tray icon in a background thread. Returns the icon or None."""
    if pystray is None:
        return None

    menu = pystray.Menu(
        pystray.MenuItem("Show / Hide", lambda: on_show()),
        pystray.MenuItem("Quit", lambda: on_quit()),
    )
    icon = pystray.Icon("abhi_ai", _make_icon_image(), "ABHI AI", menu)
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def register_hotkey(hotkey_str: str, callback):
    """Register a global hotkey. Returns True if successful."""
    if keyboard is None:
        return False
    try:
        # keyboard lib uses '+' separated combos, e.g. "ctrl+alt+space"
        combo = hotkey_str.replace("<", "").replace(">", "")
        keyboard.add_hotkey(combo, callback)
        return True
    except Exception:
        return False
