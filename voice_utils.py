"""
Voice helpers: list real microphones, safely open one (never crash the app
if a device is missing/busy), speech-to-text, and optional text-to-speech.
"""

from __future__ import annotations

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


def list_microphones() -> list[tuple[int, str]]:
    """Return [(device_index, device_name), ...]. Empty list if none/unavailable."""
    if sr is None:
        return []
    try:
        names = sr.Microphone.list_microphone_names()
        return list(enumerate(names))
    except Exception:
        return []


def open_microphone(device_index: int | None = None):
    """
    Try to open a microphone. Returns (microphone_or_None, message).
    Never raises — always returns a status message you can show the user.
    """
    if sr is None:
        return None, ("'SpeechRecognition' / 'pyaudio' install nahi hai. "
                       "`pip install SpeechRecognition pyaudio` chalao.")
    mics = list_microphones()
    if not mics:
        return None, ("Koi microphone detect nahi hua. OS-level mic "
                       "permission (Windows: Settings > Privacy > Microphone) "
                       "check karo, ya headset/mic connect karke app restart karo.")
    try:
        mic = sr.Microphone(device_index=device_index)
        # quick sanity check: opening the stream briefly
        with mic as source:
            pass
        name = mics[device_index][1] if device_index is not None else "system default"
        return mic, f"Mic ready: {name}"
    except Exception as e:
        return None, f"Mic khulte waqt error: {e}"


# Lower energy_threshold = the mic reacts to quieter sounds.
# (Google's default recognizer sits around 300, which misses soft speech.)
SENSITIVITY_LEVELS = {
    "low": 400,     # only clear, close-up speech — ignores background noise
    "medium": 200,
    "high": 60,     # catches very quiet / distant speech (more false triggers possible)
}


def configure_recognizer(recognizer, sensitivity: str = "high"):
    """Tune the recognizer so it picks up quiet speech quickly."""
    recognizer.dynamic_energy_threshold = True
    # how much silence marks the end of a phrase — shorter = snappier response
    recognizer.pause_threshold = 0.6
    # minimum volume to even consider the start of a phrase — lower = more sensitive
    recognizer.phrase_threshold = 0.1
    recognizer.non_speaking_duration = 0.3
    recognizer.energy_threshold = SENSITIVITY_LEVELS.get(sensitivity, 200)


def listen_once(recognizer, microphone, language: str = "hi-IN",
                 sensitivity: str = "high",
                 timeout: int = 8, phrase_time_limit: int = 15) -> str:
    """Capture one utterance and transcribe it. Returns '' if nothing understood."""
    configure_recognizer(recognizer, sensitivity)
    max_threshold = SENSITIVITY_LEVELS.get(sensitivity, 200)
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        # ambient calibration can push the threshold back up in a noisy room —
        # cap it so quiet speech still triggers listening
        recognizer.energy_threshold = min(recognizer.energy_threshold, max_threshold)
        audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    try:
        return recognizer.recognize_google(audio, language=language)
    except sr.UnknownValueError:
        return ""
    except sr.RequestError as e:
        return f"[STT error] {e}"


class TTSEngine:
    """Thin wrapper so the rest of the app doesn't care if pyttsx3 is missing."""

    def __init__(self):
        self.engine = None
        if pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", 175)
            except Exception:
                self.engine = None

    @property
    def available(self) -> bool:
        return self.engine is not None

    def speak(self, text: str):
        if not self.engine or not text:
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception:
            pass
