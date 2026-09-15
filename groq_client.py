from __future__ import annotations

import requests

# Aapka live Render cloud backend URL
BACKEND_URL = "https://floating-ai-1.onrender.com"


def ask_groq(user_text: str, extra_system: str = "") -> str:
    """
    Sends the prompt to the ABHI AI cloud backend hosted on Render.
    """
    if not user_text.strip():
        return ""
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/ask",
            json={"text": user_text, "extra_system": extra_system},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("answer", "No answer found.")
        else:
            try:
                err_data = response.json()
                return f"[Server Error {response.status_code}]: {err_data.get('error', response.text)}"
            except Exception:
                return f"[Server Error {response.status_code}]: {response.text}"
    except Exception as e:
        return f"[Connection Error]: {e}"


def ask_groq_translate(raw_text: str) -> tuple[str, str]:
    """
    Take a raw speech-to-text transcript and return
    (hinglish_transcript, english_answer) via the cloud backend.
    """
    if not raw_text.strip():
        return raw_text, ""

    try:
        response = requests.post(
            f"{BACKEND_URL}/translate",
            json={"text": raw_text},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            hinglish = (data.get("hinglish") or raw_text).strip()
            answer = (data.get("answer") or "").strip()
            return hinglish, answer
        else:
            # Fallback to standard ask if translate endpoint fails
            fallback_ans = ask_groq(raw_text)
            return raw_text, fallback_ans
    except Exception as e:
        fallback_ans = ask_groq(raw_text)
        return raw_text, fallback_ans
