"""Run:  python check_gemini.py   (prints status codes only, never your key)"""
import os, requests
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("GEMINI_API_KEY")
if not key: raise SystemExit("GEMINI_API_KEY is missing from .env")
first = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
models = [first] + [m for m in ("gemini-flash-latest", "gemini-3.5-flash", "gemini-3.5-flash-lite") if m != first]
for m in models:
    try:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                          headers={"x-goog-api-key": key}, json={"contents": [{"parts": [{"text": "Say OK"}]}]}, timeout=20)
        try: msg = r.json().get("error", {}).get("message", "")[:90]
        except Exception: msg = ""
        print(f"{m:26} -> {r.status_code} {msg}")
        if r.status_code == 200:
            print(f"\nWORKS. Put this in .env:  GEMINI_MODEL={m}"); break
    except Exception as e:
        print(f"{m:26} -> {type(e).__name__}")
else:
    print("\nNo model answered. Google is likely busy: try again in a few minutes. The app still works in template mode.")
