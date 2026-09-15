"""
Persistent settings for the Floating AI app.

Two layers:
  - .env            -> secrets (GROQ_API_KEY) + default model
  - settings.json    -> user-adjustable app settings (tesseract path, mic
                         device index, TTS on/off, hotkey, theme, etc.)
                         Lives next to app.py so it survives restarts.
"""

import os
import json
from dotenv import load_dotenv, set_key, find_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "tesseract_cmd": "",          # empty = auto-detect
    "mic_device_index": None,     # None = system default mic
    "tts_enabled": False,
    "hotkey_enabled": True,
    "hotkey": "<ctrl>+<alt>+space",
    "theme": "dark",
    "stt_language": "hi-IN",      # speech-to-text language (Hindi/Hinglish)
    "mic_sensitivity": "high",    # low / medium / high — high catches quiet sounds
}

# Ensure .env exists so python-dotenv / set_key has a file to write to
if not os.path.exists(ENV_PATH):
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("GROQ_API_KEY=\nGROQ_MODEL=openai/gpt-oss-20b\n")

load_dotenv(ENV_PATH)


def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            settings.update(saved)
        except Exception:
            pass
    return settings


def save_settings(settings: dict) -> None:
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_groq_api_key() -> str:
    load_dotenv(ENV_PATH, override=True)
    return os.getenv("GROQ_API_KEY", "")


def get_groq_model() -> str:
    load_dotenv(ENV_PATH, override=True)
    return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def set_env_value(key: str, value: str) -> None:
    """Write/update a key in the .env file (creates the file if needed)."""
    set_key(ENV_PATH, key, value)
    load_dotenv(ENV_PATH, override=True)
