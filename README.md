# ABHI AI — Floating Assistant (Advanced Edition)

Ek floating overlay window jo hamesha screen ke upar rehta hai, voice + OCR +
Groq AI ke saath. Ab ismein ek **Settings panel** hai jo Tesseract aur mic ki
common problems khud fix karne mein help karta hai.

## Features

- 🔎 Search bar + ➤ Send — text query Groq ko
- 🎤 Mic On/Off toggle
- **E** — ek baar suno (Hinglish/Hindi), transcript dikhao, English answer do
- **G** — continuous listening mode; jab tak stop na karo, sunta rehta hai
- 🖼 **OCR** — image/file se Tesseract OCR (auto-cleaned), fir AI explanation
- ⚙ **Settings** — Groq API key/model, Tesseract path (auto-detect + manual +
  "Test" button), microphone device picker + "Test Mic" button, text-to-speech
  toggle, global hotkey toggle
- 📋 Copy last answer to clipboard
- 💾 Save full chat log to a `.txt` file (`chat_logs/` folder)
- 🖥 System tray icon (minimize instead of closing) — optional
- ⌨ Global hotkey `Ctrl+Alt+Space` to show/hide from anywhere — optional

---

## 1. Setup

```bash
pip install -r requirements.txt
```

> **Windows par PyAudio dikkat de to:**
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

Advanced features (TTS, tray icon, global hotkey) optional hain — agar unki
libraries install nahi hain to app crash nahi karega, bas wo feature skip ho
jayega aur log mein ek note dikhega.

### Groq API key
App pehli baar run karne par khud `.env` bana dega. Key daalne ke 2 tareeke:
1. App khol ke **⚙ Settings** me paste karo (recommended), ya
2. `.env` file manually edit karo:
   ```
   GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
   ```
Free key: https://console.groq.com/keys

---

## 2. "Tesseract not installed" error fix

Ye error tab aata hai jab Tesseract system mein installed to hai, lekin
Python/PATH ko uska exact location nahi pata. App ab **auto-detect** karta hai
(PATH + common install locations), lekin agar phir bhi na mile:

1. Terminal mein check karo Tesseract kahan hai:
   - Windows: `where tesseract`
   - Mac/Linux: `which tesseract`
2. Agar command hi na chale (installed nahi hai), install karo:
   - **Windows**: https://github.com/UB-Mannheim/tesseract/wiki se installer
   - **Mac**: `brew install tesseract`
   - **Linux**: `sudo apt install tesseract-ocr`
3. Jo bhi path mile, app kholo → **⚙ Settings** → "Tesseract path" field mein
   paste karo (ya "Browse" se select karo) → **"Test Tesseract"** button dabao
   → "Tesseract OK" dikhna chahiye → **Save Settings**.

Hindi text OCR karna ho to `hin` language pack bhi install karo:
```bash
sudo apt install tesseract-ocr-hin      # Ubuntu/Debian
```
(Windows/Mac installer mein language selection option milta hai.)

---

## 3. "Mic not turning on" fix

Common causes aur fix, sab **⚙ Settings** panel se handle ho jaate hain:

1. **OS-level permission na di ho** — Windows: Settings → Privacy & Security →
   Microphone → apps ko allow karo. Mac: System Settings → Privacy & Security
   → Microphone.
2. **Galat device selected ho** (laptop ka built-in mic vs USB headset) —
   Settings → "Microphone device" dropdown se sahi device choose karo, fir
   **"Test Mic (3s)"** dabao. Kuch bolo — agar "✅ Sunai diya: ..." dikhe to
   sahi hai.
3. **PyAudio missing/broken** — `pip install pyaudio` (Windows par upar wala
   pipwin tareeka use karo agar error aaye).
4. Startup par app khud diagnostics chalata hai aur log box mein bata deta hai
   ki mic detect hua ya nahi — wahi sabse pehle padhna.

Mic ON/OFF button sirf app ke andar listening ko control karta hai; agar
device hi detect nahi ho raha, pehle Settings se "Test Mic" karke confirm
karo.

---

## 4. Run

```bash
python app.py
```

Title bar drag karke window move karo. `—` se minimize (tray/hotkey se wapas
lao), `✕` se fully quit.

---

## 5. Troubleshooting summary

| Problem | Fix |
|---|---|
| `model_not_found` from Groq | ⚙ Settings me model name badlo — current list: console.groq.com/docs/models |
| "Tesseract not installed" | ⚙ Settings → path daalo/Browse karo → Test Tesseract |
| Mic on nahi ho raha | ⚙ Settings → Microphone device select karo → Test Mic; OS mic permission bhi check karo |
| No system tray icon | `pip install pystray` |
| Global hotkey kaam nahi kar raha | `pip install keyboard`; kabhi-kabhi admin/root permission chahiye hota hai |
| TTS awaaz nahi aa rahi | `pip install pyttsx3`; Settings me "Speak answers aloud" checkbox on karo |

Chat logs `chat_logs/` folder mein save hote hain (💾 Save chat button se).
