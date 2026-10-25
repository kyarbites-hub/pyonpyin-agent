"""Explicit live text/TTS checks: one request each, no secret or story logging."""

import io
import argparse
import json
import re
import sys
import urllib.error
import wave
from pathlib import Path

from pyonpyin.audio import GeminiSpeechTTS
from pyonpyin.config import load_environment
from pyonpyin.gemini import GeminiClient


def safe_failure(error):
    cause = error
    while cause.__cause__ is not None:
        cause = cause.__cause__
    result = {"ok": False, "error_type": type(error).__name__}
    if isinstance(cause, urllib.error.HTTPError):
        result["http_status"] = cause.code
    elif isinstance(cause, (urllib.error.URLError, OSError)):
        result["network_error"] = True
        result["network_error_type"] = type(getattr(cause, "reason", cause)).__name__
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-only", action="store_true", help="Check text without another speech request")
    options = parser.parse_args()
    load_environment()
    results = {}
    try:
        client = GeminiClient(attempts=1)
        response = client._request(
            'Return only JSON with one key "message" containing one short Burmese Unicode greeting. '
            'Use at most one sentence.'
        )
        if not isinstance(response.get("message"), str) or not re.search(r"[\u1000-\u109f]", response["message"]):
            raise ValueError("Myanmar Unicode was missing.")
        results["text"] = {"ok": True, "model": client.model, "myanmar_unicode": True}
    except Exception as error:
        results["text"] = safe_failure(error)
    if options.text_only:
        print(json.dumps(results))
        return 0 if results["text"]["ok"] else 1
    if results["text"].get("network_error") or results["text"].get("http_status") == 401:
        print(json.dumps(results))
        return 1
    try:
        provider = GeminiSpeechTTS()
        audio = provider.synthesize_bytes("မင်္ဂလာပါ။ ပုံပြင်ကမ္ဘာမှ ကြိုဆိုပါတယ်။")
        with wave.open(io.BytesIO(audio), "rb") as recording:
            duration = round(recording.getnframes() / recording.getframerate(), 2)
        path = Path("data/runtime/checks/gemini-greeting.wav")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(audio)
        results["speech"] = {"ok": True, "model": provider.model, "seconds": duration,
                             "preview_path": str(path)}
    except Exception as error:
        results["speech"] = safe_failure(error)
    print(json.dumps(results))
    return 0 if all(item["ok"] for item in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
