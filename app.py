"""
Floating AI Assistant — Advanced Edition
------------------------------------------
Ek floating overlay jo hamesha screen ke upar rehta hai:

  - Search bar + Send            -> text query Groq ko
  - Mic On/Off                   -> voice listening master switch
  - E button                     -> ek baar suno, Hinglish/Hindi transcript
                                     dikhao, fir English answer do
  - G button                     -> continuous listening ("G-mood"); jab tak
                                     stop na karo, sunta rehta hai aur turant
                                     jawaab deta hai (maths/coding/anything)
  - OCR button                   -> image/file se Tesseract OCR, clean text,
                                     fir Groq se explanation/answer
  - Settings (⚙)                 -> Tesseract path (auto-detect + manual +
                                     test), microphone device picker + test,
                                     Groq API key/model, text-to-speech toggle,
                                     global hotkey toggle
  - Copy / Save chat             -> answers copy karo ya poora log .txt me save
  - System tray + global hotkey  -> window ko background me minimize karo,
                                     hotkey se wapas dikhao (agar pystray /
                                     keyboard installed hain)

Run:
    pip install -r requirements.txt
    python app.py
"""

from __future__ import annotations

import os
import sys
import math
import random
import time
import threading
import queue
import traceback
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

import config
import ocr_utils
import voice_utils
from groq_client import ask_groq, ask_groq_translate
import tray

try:
    import speech_recognition as sr
except Exception:
    sr = None


LOG_DIR = os.path.join(config.BASE_DIR, "chat_logs")

# ---- Theme ---------------------------------------------------------------
BG = "#0b0e16"
PANEL = "#141824"
PANEL_ALT = "#1b2030"
PANEL_ALT_HOVER = "#242b40"
ACCENT = "#5b8cff"
ACCENT_HOVER = "#7aa2ff"
TEXT = "#eef1f8"
TEXT_DIM = "#8993ab"
SUCCESS = "#31d0aa"
ERROR = "#ff5c6c"
WARN = "#ffb454"
HINGLISH_COLOR = "#7CFFCB"   # mint/teal — spoken transcript (Hinglish)
ENGLISH_COLOR = "#FFD37A"   # amber/gold — AI's English answer
USER_TEXT_COLOR = "#9fb3d9"  # soft blue — what the user typed/said
FONT_UI = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_MONO = ("Consolas", 9)


def add_hover(widget, base_bg, hover_bg):
    widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.config(bg=base_bg))


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: "FloatingAIApp"):
        super().__init__(parent.root)
        self.parent = parent
        self.title("Settings")
        self.geometry("420x480")
        self.configure(bg="#0b0e16")
        self.resizable(False, False)
        self.attributes("-topmost", True)

        settings = config.load_settings()
        pad = {"padx": 10, "pady": (10, 2)}

        # ---- Groq API key / model
        tk.Label(self, text="Groq API Key", bg="#0b0e16", fg="#eef1f8",
                 anchor="w").pack(fill="x", **pad)
        self.api_key_var = tk.StringVar(value=config.get_groq_api_key())
        tk.Entry(self, textvariable=self.api_key_var, show="•", bg="#141824",
                 fg="#eef1f8", insertbackground="#eef1f8").pack(fill="x", padx=10)

        tk.Label(self, text="Groq Model", bg="#0b0e16", fg="#eef1f8",
                 anchor="w").pack(fill="x", **pad)
        self.model_var = tk.StringVar(value=config.get_groq_model())
        tk.Entry(self, textvariable=self.model_var, bg="#141824", fg="#eef1f8",
                 insertbackground="#eef1f8").pack(fill="x", padx=10)
        tk.Label(self, text="e.g. openai/gpt-oss-20b — full list: "
                             "console.groq.com/docs/models",
                 bg="#0b0e16", fg="#8993ab", font=("Segoe UI", 7),
                 anchor="w", wraplength=380, justify="left").pack(fill="x", padx=10)

        # ---- Tesseract
        tk.Label(self, text="Tesseract path (blank = auto-detect)",
                 bg="#0b0e16", fg="#eef1f8", anchor="w").pack(fill="x", **pad)
        row = tk.Frame(self, bg="#0b0e16")
        row.pack(fill="x", padx=10)
        self.tess_var = tk.StringVar(value=settings.get("tesseract_cmd", ""))
        tk.Entry(row, textvariable=self.tess_var, bg="#141824", fg="#eef1f8",
                 insertbackground="#eef1f8").pack(side="left", fill="x", expand=True)
        tk.Button(row, text="Browse", command=self._browse_tesseract,
                  bg="#1b2030", fg="#eef1f8", bd=0).pack(side="left", padx=(6, 0))
        tk.Button(self, text="Test Tesseract", command=self._test_tesseract,
                  bg="#5b8cff", fg="white", bd=0).pack(fill="x", padx=10, pady=(4, 0))
        self.tess_status = tk.Label(self, text="", bg="#0b0e16", fg="#31d0aa",
                                     anchor="w", wraplength=380, justify="left",
                                     font=("Segoe UI", 8))
        self.tess_status.pack(fill="x", padx=10, pady=(2, 0))

        # ---- Microphone
        tk.Label(self, text="Microphone device", bg="#0b0e16", fg="#eef1f8",
                 anchor="w").pack(fill="x", **pad)
        mics = voice_utils.list_microphones()
        self.mic_options = ["System default"] + [f"{i}: {name}" for i, name in mics]
        self.mic_var = tk.StringVar()
        saved_idx = settings.get("mic_device_index")
        default_label = "System default"
        if saved_idx is not None:
            for i, name in mics:
                if i == saved_idx:
                    default_label = f"{i}: {name}"
        self.mic_var.set(default_label)
        ttk.Combobox(self, textvariable=self.mic_var, values=self.mic_options,
                     state="readonly").pack(fill="x", padx=10)

        tk.Label(self, text="Mic sensitivity (high = choti aawaz bhi sunega)",
                 bg="#0b0e16", fg="#eef1f8", anchor="w").pack(fill="x", padx=10, pady=(6, 2))
        self.sensitivity_var = tk.StringVar(
            value=settings.get("mic_sensitivity", "high"))
        ttk.Combobox(self, textvariable=self.sensitivity_var,
                     values=["low", "medium", "high"], state="readonly"
                     ).pack(fill="x", padx=10)

        tk.Button(self, text="Test Mic (3s)", command=self._test_mic,
                  bg="#5b8cff", fg="white", bd=0).pack(fill="x", padx=10, pady=(4, 0))
        self.mic_status = tk.Label(self, text="", bg="#0b0e16", fg="#31d0aa",
                                    anchor="w", wraplength=380, justify="left",
                                    font=("Segoe UI", 8))
        self.mic_status.pack(fill="x", padx=10, pady=(2, 0))

        # ---- Toggles
        self.tts_var = tk.BooleanVar(value=settings.get("tts_enabled", False))
        tk.Checkbutton(self, text="Speak answers aloud (text-to-speech)",
                       variable=self.tts_var, bg="#0b0e16", fg="#eef1f8",
                       selectcolor="#141824", anchor="w").pack(fill="x", padx=8, pady=(10, 0))

        self.hotkey_var = tk.BooleanVar(value=settings.get("hotkey_enabled", True))
        tk.Checkbutton(self, text="Enable global hotkey (Ctrl+Alt+Space to show/hide)",
                       variable=self.hotkey_var, bg="#0b0e16", fg="#eef1f8",
                       selectcolor="#141824", anchor="w").pack(fill="x", padx=8)

        # ---- Save
        tk.Button(self, text="Save Settings", command=self._save,
                  bg="#31d0aa", fg="white", bd=0, font=("Segoe UI", 10, "bold")
                  ).pack(fill="x", padx=10, pady=14, ipady=6)

    def _browse_tesseract(self):
        path = filedialog.askopenfilename(title="Select tesseract executable")
        if path:
            self.tess_var.set(path)

    def _test_tesseract(self):
        ok, msg = ocr_utils.configure_tesseract(self.tess_var.get().strip())
        self.tess_status.config(text=msg, fg="#31d0aa" if ok else "#ff5c6c")

    def _test_mic(self):
        idx = self._selected_mic_index()
        self.mic_status.config(text="Testing... bolo kuch.", fg="#eef1f8")
        self.update_idletasks()

        def run():
            mic, msg = voice_utils.open_microphone(idx)
            if not mic:
                self.mic_status.config(text=msg, fg="#ff5c6c")
                return
            try:
                recognizer = sr.Recognizer()
                heard = voice_utils.listen_once(
                    recognizer, mic, sensitivity=self.sensitivity_var.get(),
                    timeout=5, phrase_time_limit=5)
                if heard:
                    self.mic_status.config(text=f"✅ Sunai diya: {heard}", fg="#31d0aa")
                else:
                    self.mic_status.config(text="Mic kaam kar raha hai lekin kuch samajh nahi aaya.",
                                            fg="#ffb454")
            except Exception as e:
                self.mic_status.config(text=f"Error: {e}", fg="#ff5c6c")

        threading.Thread(target=run, daemon=True).start()

    def _selected_mic_index(self):
        label = self.mic_var.get()
        if label == "System default" or ":" not in label:
            return None
        return int(label.split(":")[0])

    def _save(self):
        config.set_env_value("GROQ_API_KEY", self.api_key_var.get().strip())
        config.set_env_value("GROQ_MODEL", self.model_var.get().strip() or "openai/gpt-oss-20b")

        settings = config.load_settings()
        settings["tesseract_cmd"] = self.tess_var.get().strip()
        settings["mic_device_index"] = self._selected_mic_index()
        settings["mic_sensitivity"] = self.sensitivity_var.get()
        settings["tts_enabled"] = self.tts_var.get()
        settings["hotkey_enabled"] = self.hotkey_var.get()
        config.save_settings(settings)

        self.parent.reload_after_settings()
        messagebox.showinfo("Saved", "Settings saved.", parent=self)
        self.destroy()


class FloatingAIApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ABHI AI")
        self.root.geometry("380x565+120+80")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg="#0b0e16")
        # Floating "water bubble" look: overall slight transparency everywhere,
        # plus (Windows only) true see-through for plain background areas.
        try:
            self.root.attributes("-alpha", 0.93)
        except Exception:
            pass
        try:
            self.root.wm_attributes("-transparentcolor", BG)
        except Exception:
            pass  # not supported on this OS (macOS/Linux) — silently skip

        self.settings = config.load_settings()
        self.mic_enabled = tk.BooleanVar(value=True)
        self.g_mode_running = False
        self.e_mode_running = False
        self._drag_data = {"x": 0, "y": 0}
        self.last_answer = ""

        self.ui_queue = queue.Queue()
        self._toast_queue = []
        self._toast_active = False
        self._toast_label = None
        os.makedirs(LOG_DIR, exist_ok=True)
        self.chat_log = []

        self._build_ui()
        self._poll_queue()

        self.recognizer = sr.Recognizer() if sr else None
        self.tts = voice_utils.TTSEngine()

        self._run_startup_diagnostics()
        self._setup_tray_and_hotkey()

    # ------------------------------------------------------------ diagnostics
    def _run_startup_diagnostics(self):
        def run():
            ok, msg = ocr_utils.configure_tesseract(self.settings.get("tesseract_cmd", ""))
            self.log(("✅ " if ok else "⚠️ ") + msg)

            mics = voice_utils.list_microphones()
            if not mics:
                self.log("⚠️ Koi microphone detect nahi hua — Settings (⚙) kholo "
                          "aur 'Test Mic' try karo, ya OS mic permission check karo.")
            else:
                idx = self.settings.get("mic_device_index")
                name = "system default"
                if idx is not None:
                    for i, n in mics:
                        if i == idx:
                            name = n
                self.log(f"✅ Mic ready ({len(mics)} device(s) found, using: {name}).")

            if not config.get_groq_api_key():
                self.log("⚠️ Groq API key set nahi hai — Settings (⚙) me daalo.")
        threading.Thread(target=run, daemon=True).start()

    def reload_after_settings(self):
        self.settings = config.load_settings()
        self._run_startup_diagnostics()

    # ------------------------------------------------------------ tray/hotkey
    def _setup_tray_and_hotkey(self):
        self.tray_icon = tray.start_tray(
            on_show=lambda: self.root.after(0, self._toggle_visibility),
            on_quit=lambda: self.root.after(0, self._quit),
        )
        if self.tray_icon is None:
            self.log("ℹ️ System tray ke liye `pip install pystray` karo (optional).")

        if self.settings.get("hotkey_enabled", True):
            ok = tray.register_hotkey(
                self.settings.get("hotkey", "<ctrl>+<alt>+space"),
                lambda: self.root.after(0, self._toggle_visibility),
            )
            if not ok:
                self.log("ℹ️ Global hotkey ke liye `pip install keyboard` karo "
                          "(kabhi-kabhi admin/root permission chahiye).")

    def _toggle_visibility(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
        else:
            self.root.withdraw()

    def _quit(self):
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()
        sys.exit(0)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        top = tk.Frame(self.root, bg=PANEL, height=36)
        top.pack(fill="x", side="top")
        top.bind("<ButtonPress-1>", self._start_drag)
        top.bind("<B1-Motion>", self._on_drag)

        accent_bar = tk.Frame(self.root, bg=ACCENT, height=2)
        accent_bar.pack(fill="x", side="top")

        title = tk.Label(top, text="✨ ABHI AI", bg=PANEL, fg=TEXT,
                          font=FONT_UI_BOLD)
        title.pack(side="left", padx=10, pady=6)
        title.bind("<ButtonPress-1>", self._start_drag)
        title.bind("<B1-Motion>", self._on_drag)

        close_b = tk.Button(top, text="✕", bg=PANEL, fg=TEXT_DIM, bd=0,
                             activebackground=PANEL_ALT_HOVER, activeforeground=ERROR,
                             font=FONT_UI, command=self._quit)
        close_b.pack(side="right", padx=(2, 8))
        add_hover(close_b, PANEL, PANEL_ALT_HOVER)

        min_b = tk.Button(top, text="—", bg=PANEL, fg=TEXT_DIM, bd=0,
                           activebackground=PANEL_ALT_HOVER, activeforeground=TEXT,
                           font=FONT_UI, command=lambda: self.root.withdraw())
        min_b.pack(side="right", padx=2)
        add_hover(min_b, PANEL, PANEL_ALT_HOVER)

        settings_b = tk.Button(top, text="⚙", bg=PANEL, fg=TEXT_DIM, bd=0,
                                activebackground=PANEL_ALT_HOVER, activeforeground=ACCENT,
                                font=FONT_UI, command=lambda: SettingsDialog(self))
        settings_b.pack(side="right", padx=2)
        add_hover(settings_b, PANEL, PANEL_ALT_HOVER)

        # ---- Animated "Structure Flow" decorative background strip ----
        self.flow_canvas = tk.Canvas(self.root, height=52, bg=PANEL,
                                      highlightthickness=0)
        self.flow_canvas.pack(fill="x", side="top")
        self.flow_canvas.create_text(
            10, 26, anchor="w", text="🌌 structure flow",
            fill=TEXT_DIM, font=("Segoe UI", 7), tags="label")
        self._flow_particles = [
            {"x": random.uniform(0, 380), "y": random.uniform(8, 44),
             "vx": random.uniform(-0.5, 0.5), "phase": random.uniform(0, 6.28),
             "r": random.uniform(1.5, 3)}
            for _ in range(16)
        ]
        self._animate_flow_bg()

        output_card = tk.Frame(self.root, bg=PANEL_ALT, bd=0)
        output_card.pack(fill="both", expand=True, padx=8, pady=(8, 4))
        self.output = scrolledtext.ScrolledText(
            output_card, wrap="word", bg="#0a0d14", fg="#e3e8f5",
            insertbackground="#e3e8f5", font=FONT_MONO, height=18,
            bd=0, highlightthickness=1, highlightbackground=PANEL_ALT,
            highlightcolor=ACCENT
        )
        self.output.pack(fill="both", expand=True, padx=2, pady=2)
        self.output.tag_configure("ts", foreground=TEXT_DIM, font=("Segoe UI", 7))
        self.output.tag_configure("user", foreground=USER_TEXT_COLOR)
        self.output.tag_configure("hinglish", foreground=HINGLISH_COLOR)
        self.output.tag_configure("english", foreground=ENGLISH_COLOR)
        self.output.configure(state="disabled")

        status_row = tk.Frame(self.root, bg=BG)
        status_row.pack(fill="x", padx=10)
        self.status_dot = tk.Label(status_row, text="●", bg=BG, fg=SUCCESS,
                                    font=("Segoe UI", 9))
        self.status_dot.pack(side="left")
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(status_row, textvariable=self.status_var, bg=BG, fg=TEXT_DIM,
                 anchor="w", font=("Segoe UI", 8)).pack(side="left", padx=(4, 0))

        search_row = tk.Frame(self.root, bg=BG)
        search_row.pack(fill="x", padx=8, pady=6)
        self.entry = tk.Entry(search_row, bg=PANEL, fg=TEXT,
                               insertbackground=TEXT, font=("Segoe UI", 10),
                               relief="flat", highlightthickness=1,
                               highlightbackground=PANEL_ALT, highlightcolor=ACCENT)
        self.entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self.on_send_text())
        send_b = tk.Button(search_row, text="➤", width=3, command=self.on_send_text,
                            bg=ACCENT, fg="white", bd=0, font=FONT_UI_BOLD,
                            activebackground=ACCENT_HOVER, activeforeground="white")
        send_b.pack(side="right")
        add_hover(send_b, ACCENT, ACCENT_HOVER)

        btn_row = tk.Frame(self.root, bg=BG)
        btn_row.pack(fill="x", padx=8, pady=(0, 4))

        def make_btn(parent, text, cmd):
            b = tk.Button(parent, text=text, command=cmd, bg=PANEL_ALT, fg=TEXT,
                           bd=0, font=FONT_UI, activebackground=PANEL_ALT_HOVER,
                           activeforeground=TEXT)
            add_hover(b, PANEL_ALT, PANEL_ALT_HOVER)
            return b

        self.mic_btn = make_btn(btn_row, "🎤 Mic: ON", self.toggle_mic)
        self.mic_btn.pack(side="left", fill="x", expand=True, padx=2, ipady=6)
        self.e_btn = make_btn(btn_row, "🗣 E", self.on_e_button)
        self.e_btn.pack(side="left", fill="x", expand=True, padx=2, ipady=6)
        self.g_btn = make_btn(btn_row, "🔁 G", self.toggle_g_mode)
        self.g_btn.pack(side="left", fill="x", expand=True, padx=2, ipady=6)
        self.img_btn = make_btn(btn_row, "🖼 OCR", self.on_pick_image)
        self.img_btn.pack(side="left", fill="x", expand=True, padx=2, ipady=6)

        btn_row2 = tk.Frame(self.root, bg=BG)
        btn_row2.pack(fill="x", padx=8, pady=(0, 10))
        copy_b = make_btn(btn_row2, "📋 Copy last answer", self.copy_last_answer)
        copy_b.pack(side="left", fill="x", expand=True, padx=2, ipady=5)
        save_b = make_btn(btn_row2, "💾 Save chat", self.save_chat)
        save_b.pack(side="left", fill="x", expand=True, padx=2, ipady=5)

        self.log("ABHI AI ready. Type a question, or use E / G / OCR buttons. "
                 "⚙ Settings se Tesseract path, mic device, TTS configure karo.")

    def _animate_flow_bg(self):
        """Draw a subtle flowing-particle / wave effect (~20fps), fully self-contained
        (no external assets or network calls — pure canvas drawing)."""
        c = self.flow_canvas
        c.delete("wave", "particle")
        w = c.winfo_width() or 380
        h = c.winfo_height() or 52
        t = time.time()

        wave_colors = [ACCENT, ACCENT_HOVER, "#3d63ff"]
        for i, y_frac in enumerate((0.3, 0.55, 0.8)):
            pts = []
            for x in range(-10, w + 10, 12):
                y = y_frac * h + math.sin(x * 0.045 + t * 1.3 + i * 2.1) * (h * 0.16)
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(*pts, fill=wave_colors[i % len(wave_colors)],
                               width=1, smooth=True, tags="wave")

        for p in self._flow_particles:
            p["x"] += p["vx"]
            if p["x"] < -6:
                p["x"] = w + 6
            elif p["x"] > w + 6:
                p["x"] = -6
            y = p["y"] + math.sin(t * 1.6 + p["phase"]) * 5
            r = p["r"]
            c.create_oval(p["x"] - r, y - r, p["x"] + r, y + r,
                          fill=ACCENT_HOVER, outline="", tags="particle")

        c.tag_raise("label")
        self.root.after(60, self._animate_flow_bg)

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_data["x"])
        y = self.root.winfo_y() + (event.y - self._drag_data["y"])
        self.root.geometry(f"+{x}+{y}")

    # -------------------------------------------------------------- logging
    def log_chat(self, text: str, tag: str = "user"):
        """Persistent, colored line in the main AI-chat display (never auto-hides)."""
        self.chat_log.append(text)
        self.ui_queue.put(("chat", text, tag))

    def toast(self, text: str, kind: str = "info"):
        """Transient status/system message — shows briefly then disappears on its own."""
        self.ui_queue.put(("toast", text, kind))

    def log(self, text: str):
        """Back-compat: startup diagnostics / system notices — treated as toasts."""
        kind = "error" if ("error" in text.lower() or "❌" in text) else "info"
        self.toast(text, kind=kind)

    def _poll_queue(self):
        try:
            while True:
                kind, text, tag = self.ui_queue.get_nowait()
                if kind == "chat":
                    self.output.configure(state="normal")
                    ts = datetime.now().strftime("%H:%M:%S")
                    self.output.insert("end", f"[{ts}] ", "ts")
                    self.output.insert("end", f"{text}\n\n", tag)
                    self.output.see("end")
                    self.output.configure(state="disabled")
                else:
                    self._queue_toast(text, tag)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_queue)

    # ------------------------------------------------------------ toasts
    def _queue_toast(self, text: str, kind: str):
        self._toast_queue.append((text, kind))
        if not self._toast_active:
            self._show_next_toast()

    def _show_next_toast(self):
        if not self._toast_queue:
            self._toast_active = False
            return
        self._toast_active = True
        text, kind = self._toast_queue.pop(0)
        fg = ERROR if kind == "error" else (WARN if kind == "warn" else SUCCESS)
        if self._toast_label is not None:
            try:
                self._toast_label.destroy()
            except Exception:
                pass
        lbl = tk.Label(self.output.master, text=text, bg="#0f1420", fg=fg,
                        font=FONT_UI, wraplength=340, justify="left",
                        bd=1, relief="solid", padx=8, pady=4)
        lbl.place(relx=0.5, rely=0.03, anchor="n")
        self._toast_label = lbl
        self.root.after(2200, lambda: self._hide_toast(lbl))

    def _hide_toast(self, lbl):
        try:
            lbl.destroy()
        except Exception:
            pass
        if self._toast_label is lbl:
            self._toast_label = None
        self.root.after(120, self._show_next_toast)

    def set_status(self, text: str):
        self.status_var.set(text)
        low = text.lower()
        if "error" in low or "❌" in text:
            color = ERROR
        elif "thinking" in low or "processing" in low or "recognizing" in low:
            color = ACCENT
        elif "listening" in low:
            color = WARN
        else:
            color = SUCCESS
        self.status_dot.config(fg=color)

    def copy_last_answer(self):
        if not self.last_answer:
            self.set_status("Koi answer abhi tak nahi hai.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.last_answer)
        self.set_status("Clipboard me copy ho gaya.")

    def save_chat(self):
        if not self.chat_log:
            self.set_status("Chat khaali hai.")
            return
        fname = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        path = os.path.join(LOG_DIR, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(self.chat_log))
        self.set_status(f"Saved: {path}")

    # -------------------------------------------------------------- actions
    def on_send_text(self):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, "end")
        self.log_chat(f"🧑 You: {text}", tag="user")
        threading.Thread(target=self._handle_text_query, args=(text,), daemon=True).start()

    def _handle_text_query(self, text: str):
        self.set_status("Thinking...")
        answer = ask_groq(text)
        self._emit_answer(answer)

    def _emit_answer(self, answer: str):
        answer = answer or "[Error] Model se koi jawaab nahi aaya. Dobara try karo."
        self.last_answer = answer
        self.log_chat(f"🤖 AI: {answer}", tag="english")
        self.set_status("Ready.")
        if self.settings.get("tts_enabled") and self.tts.available:
            threading.Thread(target=self.tts.speak, args=(answer,), daemon=True).start()

    def toggle_mic(self):
        self.mic_enabled.set(not self.mic_enabled.get())
        if self.mic_enabled.get():
            self.mic_btn.config(text="🎤 Mic: ON")
        else:
            self.mic_btn.config(text="🔇 Mic: OFF")
            self.g_mode_running = False
            self.e_mode_running = False

    def _get_mic(self):
        idx = self.settings.get("mic_device_index")
        return voice_utils.open_microphone(idx)

    def _check_mic_ready(self) -> bool:
        if not sr or not self.recognizer:
            self.log("[Error] 'speechrecognition' / 'pyaudio' install nahi hai. "
                      "`pip install SpeechRecognition pyaudio` chalao.")
            return False
        if not self.mic_enabled.get():
            self.log("Mic OFF hai. Pehle 🎤 Mic button se ON karo.")
            return False
        return True

    def on_e_button(self):
        """E mode: continuous AI translator. Keeps listening on the mic (any
        language), writes what it heard as a clean Hinglish transcript, and
        gives an English answer — until pressed again."""
        if self.e_mode_running:
            self.e_mode_running = False
            self.e_btn.config(text="🗣 E", bg=PANEL_ALT)
            self.set_status("E-mode stopped.")
            return
        if not self._check_mic_ready():
            return
        self.e_mode_running = True
        self.e_btn.config(text="🔴 E (listening)", bg=ACCENT)
        threading.Thread(target=self._e_mode_loop, daemon=True).start()

    def _e_mode_loop(self):
        mic, msg = self._get_mic()
        if not mic:
            self.toast(f"[Mic error] {msg}", kind="error")
            self.e_mode_running = False
            self.root.after(0, lambda: self.e_btn.config(text="🗣 E", bg=PANEL_ALT))
            return

        self.toast("E-mode ON: kisi bhi language me bolo, continuously sunta rahega.")
        while self.e_mode_running and self.mic_enabled.get():
            try:
                self.set_status("Listening...")
                heard = voice_utils.listen_once(
                    self.recognizer, mic,
                    language=self.settings.get("stt_language", "hi-IN"),
                    sensitivity=self.settings.get("mic_sensitivity", "high"))
                if not self.e_mode_running:
                    break
                if not heard:
                    continue
                self.set_status("Translating...")
                hinglish, answer = ask_groq_translate(heard)
                self.log_chat(f"🎙 {hinglish}", tag="hinglish")
                self._emit_answer(answer)
            except Exception as e:
                self.toast(f"[Error] {e}", kind="error")
        self.e_mode_running = False
        self.root.after(0, lambda: self.e_btn.config(text="🗣 E", bg=PANEL_ALT))
        self.set_status("Ready.")

    def toggle_g_mode(self):
        if self.g_mode_running:
            self.g_mode_running = False
            self.g_btn.config(text="🔁 G", bg="#1b2030")
            self.set_status("G-mode stopped.")
            return
        if not self._check_mic_ready():
            return
        self.g_mode_running = True
        self.g_btn.config(text="🔴 G (listening)", bg="#5b8cff")
        threading.Thread(target=self._g_mode_loop, daemon=True).start()

    def _g_mode_loop(self):
        mic, msg = self._get_mic()
        if not mic:
            self.log(f"[Mic error] {msg}")
            self.g_mode_running = False
            self.root.after(0, lambda: self.g_btn.config(text="🔁 G", bg="#1b2030"))
            return

        self.log("G-mode ON: continuously sun raha hoon. Maths, coding, kuch bhi poocho.")
        while self.g_mode_running and self.mic_enabled.get():
            try:
                self.set_status("Listening...")
                heard = voice_utils.listen_once(
                    self.recognizer, mic,
                    language=self.settings.get("stt_language", "hi-IN"),
                    sensitivity=self.settings.get("mic_sensitivity", "high"))
                if not self.g_mode_running:
                    break
                if not heard:
                    continue
                self.log_chat(f"🎙 You: {heard}", tag="user")
                self.set_status("Thinking...")
                answer = ask_groq(
                    heard,
                    extra_system="Continuous listening mode: answer any "
                                 "question - maths, coding, general knowledge, "
                                 "anything - clearly and in English."
                )
                self._emit_answer(answer)
            except Exception as e:
                self.toast(f"[Error] {e}", kind="error")
        self.g_mode_running = False
        self.root.after(0, lambda: self.g_btn.config(text="🔁 G", bg="#1b2030"))
        self.set_status("Ready.")

    def on_pick_image(self):
        path = filedialog.askopenfilename(
            title="Select image / file for OCR",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.tiff *.webp"),
                       ("All files", "*.*")]
        )
        if not path:
            return
        threading.Thread(target=self._handle_ocr, args=(path,), daemon=True).start()

    def _handle_ocr(self, path: str):
        ok, msg = ocr_utils.configure_tesseract(self.settings.get("tesseract_cmd", ""))
        if not ok:
            self.log(f"[Tesseract error] {msg}")
            return
        try:
            self.set_status("OCR processing...")
            self.log(f"📄 Reading file: {os.path.basename(path)}")
            neat_text = ocr_utils.ocr_image(path)
            if not neat_text:
                self.log("OCR ko koi text nahi mila is image mein.")
                self.set_status("Ready.")
                return
            self.log_chat(f"📄 OCR extracted text:\n{neat_text}", tag="user")
            self.set_status("Thinking...")
            answer = ask_groq(
                neat_text,
                extra_system="The following text was extracted from an image "
                             "via OCR. It may contain minor recognition noise. "
                             "Understand it, correct obvious OCR errors "
                             "mentally, and give a clear, useful answer/"
                             "explanation/solution."
            )
            self._emit_answer(answer)
        except Exception as e:
            self.log(f"[OCR error] {e}\n{traceback.format_exc(limit=1)}")
            self.set_status("Ready.")


def main():
    root = tk.Tk()
    app = FloatingAIApp(root)
    root.protocol("WM_DELETE_WINDOW", app._quit)
    root.mainloop()


if __name__ == "__main__":
    main()