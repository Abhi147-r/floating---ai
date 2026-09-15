"""
ABHI AI — cloud backend (Render deployment)
--------------------------------------------
Wraps the Groq calls as a small HTTP API. Deploy THIS on Render — not the
desktop app (Tkinter/mic/OCR/tray can't run on a headless server).

Endpoints:
  GET  /health              -> {"status": "ok"}
  POST /ask                 -> body: {"text": "...", "extra_system": ""}
                                resp: {"answer": "..."}
  POST /translate            -> body: {"text": "..."}
                                resp: {"hinglish": "...", "answer": "..."}

Env vars (set these in the Render dashboard, not in code):
  GROQ_API_KEY        (required) your Groq key
  GROQ_MODEL          (optional) default "openai/gpt-oss-20b"
  APP_SHARED_SECRET   (optional) if set, callers must send header
                       "X-API-Key: <secret>" — protects your Groq quota
                       from random internet traffic once the URL is public.
"""

from __future__ import annotations

import os
import json
from functools import wraps

from flask import Flask, request, jsonify

try:
    from groq import Groq
except Exception:
    Groq = None

app = Flask(__name__)

SYSTEM_PROMPT = (
    "You are ABHI AI, a fast, helpful assistant. You were created and "
    "taught by Abhimanyu Rana — if the user ever asks who made you, trained "
    "you, or built you, answer clearly that Abhimanyu Rana made you. "
    "The user may speak or type in Hinglish (Hindi written in Roman/English "
    "letters) or Hindi. Understand the intent regardless of language, and "
    "always reply in clear, correct English, unless the user explicitly "
    "asks for another language. Keep answers concise but complete, and use "
    "step-by-step reasoning for maths/coding."
)

TRANSLATE_SYSTEM_PROMPT = (
    "You are ABHI AI, a real-time voice translator. You were created and "
    "taught by Abhimanyu Rana — if the user ever asks who made/trained/"
    "built you, say clearly that Abhimanyu Rana made you. "
    "You will receive a raw speech-to-text transcript in any language or "
    "script, possibly with recognition noise. Do two things:\n"
    "1. Rewrite exactly what was said in Hinglish (Hindi in plain Roman "
    "letters, natural spoken style) — just a clean transcript, not an "
    "answer.\n"
    "2. Give a clear, complete answer in English.\n"
    "Respond ONLY with strict JSON, no markdown, no code fences: "
    '{"hinglish": "...", "answer": "..."}'
)

FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "qwen/qwen3.6-27b",
    "groq/compound-mini",
]


def _strip_json_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    return raw.strip()


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        secret = os.environ.get("APP_SHARED_SECRET", "").strip()
        if secret:
            sent = request.headers.get("X-API-Key", "")
            if sent != secret:
                return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


def _client_and_model():
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b").strip()
    if Groq is None:
        return None, model, "`groq` package install nahi hai."
    if not api_key:
        return None, model, "GROQ_API_KEY env var set nahi hai (Render dashboard me daalo)."
    return Groq(api_key=api_key), model, None


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/ask")
@require_api_key
def ask():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    extra_system = body.get("extra_system") or ""
    if not text:
        return jsonify({"error": "'text' is required"}), 400

    client, primary_model, err = _client_and_model()
    if err:
        return jsonify({"error": err}), 500

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + extra_system},
                {"role": "user", "content": text}]
    candidates = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    last_error = None

    for i, model in enumerate(candidates):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=0.4, max_tokens=2048,
            )
            choice = resp.choices[0]
            answer = (choice.message.content or "").strip()
            if not answer:
                last_error = f"'{model}' returned an empty response"
                continue
            if i > 0:
                answer = (f"[Note: used fallback model '{model}']\n\n" + answer)
            return jsonify({"answer": answer})
        except Exception as e:
            msg = str(e)
            last_error = e
            recoverable = ("model_not_found" in msg or "does not exist" in msg
                           or "404" in msg or "decommissioned" in msg)
            if recoverable:
                continue
            return jsonify({"error": str(e)}), 502

    return jsonify({"error": f"all models failed: {last_error}"}), 502


@app.post("/translate")
@require_api_key
def translate():
    body = request.get_json(silent=True) or {}
    raw_text = (body.get("text") or "").strip()
    if not raw_text:
        return jsonify({"error": "'text' is required"}), 400

    client, primary_model, err = _client_and_model()
    if err:
        return jsonify({"error": err}), 500

    messages = [{"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text}]
    candidates = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    last_error = None

    for model in candidates:
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=0.3, max_tokens=2048,
            )
            content = resp.choices[0].message.content
            if not content or not content.strip():
                last_error = f"'{model}' returned an empty response"
                continue
            raw = _strip_json_fences(content)
            try:
                data = json.loads(raw)
                hinglish = (data.get("hinglish") or raw_text).strip()
                answer = (data.get("answer") or "").strip() or raw
                return jsonify({"hinglish": hinglish, "answer": answer})
            except json.JSONDecodeError:
                return jsonify({"hinglish": raw_text, "answer": raw})
        except Exception as e:
            msg = str(e)
            last_error = e
            recoverable = ("model_not_found" in msg or "does not exist" in msg
                           or "404" in msg or "decommissioned" in msg)
            if recoverable:
                continue
            return jsonify({"error": str(e)}), 502

    return jsonify({"error": f"all models failed: {last_error}"}), 502


if __name__ == "__main__":
    # local test only — Render runs this via gunicorn (see Procfile)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)