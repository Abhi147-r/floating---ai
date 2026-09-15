from __future__ import annotations

import json

try:
    from groq import Groq
except Exception:
    Groq = None

import config

SYSTEM_PROMPT = (
    "You are ABHI AI, a fast, helpful assistant embedded in a floating "
    "desktop widget. You were created and taught by Abhimanyu Rana — if the "
    "user ever asks who made you, trained you, or built you, answer clearly "
    "that Abhimanyu Rana made you. "
    "The user may speak or type in Hinglish (Hindi written in Roman/English "
    "letters) or Hindi. Understand the intent regardless of language, and "
    "always reply in clear, correct English, unless the user explicitly asks "
    "for another language. You can help with anything: maths, coding, general "
    "knowledge, explanations of text extracted from images (OCR), etc. Keep "
    "answers concise but complete, and use step-by-step reasoning for "
    "maths/coding."
)

TRANSLATE_SYSTEM_PROMPT = (
    "You are ABHI AI, a real-time voice translator inside a floating desktop "
    "widget. You were created and taught by Abhimanyu Rana — if the user "
    "ever asks who made/trained/built you, say clearly that Abhimanyu Rana "
    "made you. "
    "You will receive a raw speech-to-text transcript. It may be in any "
    "language or script (Hindi, Hinglish, English, or mixed) and may contain "
    "minor recognition noise. Do two things:\n"
    "1. Rewrite exactly what was said in Hinglish — Hindi words spelled out "
    "in plain Roman/English letters, natural spoken style. This is just a "
    "clean transcript of what the user said, not an answer.\n"
    "2. Give a clear, complete, well-reasoned answer to what the user said, "
    "written in English.\n"
    "Respond ONLY with strict JSON and nothing else — no markdown, no code "
    "fences, no preamble — in exactly this shape: "
    "{\"hinglish\": \"...\", \"answer\": \"...\"}"
)


def _strip_json_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    return raw.strip()


# If the configured model is unavailable (renamed/deprecated/rate-limited),
# automatically try these free-tier models in order instead of just failing.
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
    "qwen/qwen3.6-27b",
    "groq/compound-mini",
]


def ask_groq(user_text: str, extra_system: str = "") -> str:
    api_key = config.get_groq_api_key()
    primary_model = config.get_groq_model()

    if Groq is None:
        return "[Error] `groq` package install nahi hai. `pip install groq` chalao."
    if not api_key:
        return ("[Error] GROQ_API_KEY set nahi hai. Settings me apna free Groq "
                "API key daalo (https://console.groq.com/keys).")

    client = Groq(api_key=api_key)
    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n" + extra_system}]
    messages.append({"role": "user", "content": user_text})

    candidates = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    last_error = None

    for i, model in enumerate(candidates):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.4,
                max_tokens=2048,
            )
            choice = resp.choices[0]
            answer = (choice.message.content or "").strip()
            if not answer:
                # Reasoning models can burn the whole token budget on hidden
                # "thinking" and leave nothing for the final answer, especially
                # on messy/garbled input (e.g. raw OCR text). Treat as
                # recoverable and try the next model instead of returning blank.
                last_error = (f"'{model}' returned an empty response "
                               f"(finish_reason={getattr(choice, 'finish_reason', '?')})")
                continue
            if i > 0:
                answer = (f"[Note: '{primary_model}' is unavailable right now — "
                          f"used fallback model '{model}'. Update it in Settings "
                          f"to stop seeing this note.]\n\n" + answer)
            return answer
        except Exception as e:
            msg = str(e)
            last_error = e
            recoverable = ("model_not_found" in msg or "does not exist" in msg
                           or "404" in msg or "decommissioned" in msg)
            if recoverable:
                continue  # try the next candidate model
            # Non-model errors (bad key, network, rate limit) won't be fixed
            # by switching models — stop and report immediately.
            return f"[Groq error] {e}"

    return (f"[Groq error] Saare models try kiye, sab fail ho gaye. "
            f"Last error: {last_error}\nCheck karo: "
            f"https://console.groq.com/docs/models")


def ask_groq_translate(raw_text: str) -> tuple[str, str]:
    """
    Take a raw speech-to-text transcript (any language/script) and return
    (hinglish_transcript, english_answer) in a single LLM call.
    Falls back gracefully if the key/package is missing or JSON parsing fails.
    """
    api_key = config.get_groq_api_key()
    primary_model = config.get_groq_model()

    if Groq is None:
        return raw_text, "[Error] `groq` package install nahi hai. `pip install groq` chalao."
    if not api_key:
        return raw_text, ("[Error] GROQ_API_KEY set nahi hai. Settings me apna free "
                           "Groq API key daalo (https://console.groq.com/keys).")

    client = Groq(api_key=api_key)
    messages = [
        {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
        {"role": "user", "content": raw_text},
    ]

    candidates = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]
    last_error = None

    for model in candidates:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=2048,
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
                return hinglish, answer
            except json.JSONDecodeError:
                # Model replied but not in strict JSON — show raw text as the
                # answer rather than losing the response entirely.
                return raw_text, raw
        except Exception as e:
            msg = str(e)
            last_error = e
            recoverable = ("model_not_found" in msg or "does not exist" in msg
                           or "404" in msg or "decommissioned" in msg)
            if recoverable:
                continue
            return raw_text, f"[Groq error] {e}"

    return raw_text, (f"[Groq error] Saare models try kiye, sab fail ho gaye. "
                       f"Last error: {last_error}")
