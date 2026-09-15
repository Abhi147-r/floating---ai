"""
OCR helpers: auto-detect Tesseract even if it's installed but not on PATH
(the #1 cause of "tesseract is not installed" errors), plus image cleanup
for better OCR accuracy.
"""

from __future__ import annotations

import os
import re
import shutil
import platform

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from PIL import Image, ImageOps, ImageFilter
except Exception:
    Image = None

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None


# Common install locations per OS, checked if `tesseract` isn't on PATH.
COMMON_PATHS = {
    "Windows": [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%USERPROFILE%\AppData\Local\Tesseract-OCR\tesseract.exe"),
    ],
    "Darwin": [  # macOS (Homebrew, both Intel and Apple Silicon paths)
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
    ],
    "Linux": [
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        "/snap/bin/tesseract",
    ],
}


def find_tesseract(explicit_path: str = "") -> str:
    """
    Return a working tesseract executable path, or "" if none found.
    Order: explicit override (from settings) -> PATH -> common OS locations.
    """
    if explicit_path and os.path.isfile(explicit_path):
        return explicit_path

    on_path = shutil.which("tesseract")
    if on_path:
        return on_path

    system = platform.system()
    for candidate in COMMON_PATHS.get(system, []):
        if os.path.isfile(candidate):
            return candidate

    return ""


def configure_tesseract(explicit_path: str = "") -> tuple[bool, str]:
    """
    Locate tesseract and point pytesseract at it.
    Returns (ok, message).
    """
    if pytesseract is None:
        return False, "pytesseract package install nahi hai (`pip install pytesseract`)."

    path = find_tesseract(explicit_path)
    if not path:
        return False, (
            "Tesseract binary nahi mila. Agar install hai to Settings me "
            "iska exact path daalo (e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe "
            "ya jo `which tesseract` / `where tesseract` output de)."
        )

    pytesseract.pytesseract.tesseract_cmd = path
    try:
        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract OK ({path}) — version {version}"
    except Exception as e:
        return False, f"Tesseract path mila ({path}) lekin run nahi ho raha: {e}"


def clean_ocr_text(raw: str) -> str:
    """Turn raw OCR output into neat, model-ready text."""
    if not raw:
        return ""
    text = raw.replace("\r", "\n")
    # join words that were hyphen-broken across a line ("exam-\nple" -> "example")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # collapse single line-breaks inside a paragraph into spaces, keep blank
    # lines as paragraph separators
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # strip stray control/garbage characters but keep Devanagari + punctuation
    text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u0900-\u097F]", "", text)
    # drop isolated 1-character "words" that are almost always OCR noise
    text = re.sub(r"(?<!\S)[^\w\s](?!\S)", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _deskew(gray_np):
    """Straighten slightly rotated scans/photos (OpenCV path only)."""
    coords = np.column_stack(np.where(gray_np < 250))
    if coords.shape[0] < 20:
        return gray_np
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.3:  # not worth rotating
        return gray_np
    (h, w) = gray_np.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(gray_np, m, (w, h), flags=cv2.INTER_CUBIC,
                           borderMode=cv2.BORDER_REPLICATE)


def preprocess_image_for_ocr(path: str):
    """
    Clean an image up for maximum OCR accuracy: upscale, denoise, deskew,
    and binarize. Uses OpenCV when available (better quality); otherwise
    falls back to a PIL-only pipeline that still works well.
    """
    if cv2 is not None and np is not None:
        img = cv2.imread(path)
        if img is None:
            # cv2 can't read some formats (e.g. some PNGs) — fall back to PIL
            return _preprocess_with_pil(path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        h, w = gray.shape[:2]
        if max(h, w) < 1800:
            scale = 1800 / max(h, w)
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)),
                               interpolation=cv2.INTER_CUBIC)

        gray = cv2.fastNlMeansDenoising(gray, h=15)
        gray = _deskew(gray)
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        # Otsu binarization — automatically finds the best black/white cutoff
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return Image.fromarray(binary)

    return _preprocess_with_pil(path)


def _preprocess_with_pil(path: str):
    """Fallback pipeline when OpenCV isn't installed."""
    img = Image.open(path)
    img = img.convert("L")
    w, h = img.size
    if max(w, h) < 1800:
        scale = 1800 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.MedianFilter(size=3))  # light denoise
    img = img.filter(ImageFilter.SHARPEN)
    img = img.point(lambda p: 255 if p > 150 else 0)
    return img


def ocr_image(path: str, lang: str = "eng+hin") -> str:
    img = preprocess_image_for_ocr(path)
    try:
        raw = pytesseract.image_to_string(img, lang=lang, config="--psm 6")
    except pytesseract.TesseractError:
        # 'hin' language pack may not be installed -> fall back to English only
        raw = pytesseract.image_to_string(img, lang="eng", config="--psm 6")
    return clean_ocr_text(raw)
