"""Configurable TTS adapter; no unverified Burmese voice is assumed."""

import os
import io
import re
import wave
import base64
import binascii
import json
from xml.sax.saxutils import escape
import urllib.error
import urllib.request


class AudioUnavailable(RuntimeError):
    pass


MAX_AUDIO_BYTES = 25 * 1024 * 1024


def validate_audio(data, suffix):
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ValueError("Audio must be non-empty and at most 25 MiB.")
    if suffix == ".wav":
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                if audio.getnframes() < 1 or not audio.readframes(1):
                    raise ValueError("WAV audio has no samples.")
        except (wave.Error, EOFError) as exc:
            raise ValueError("Invalid PCM WAV audio.") from exc
    elif suffix == ".mp3":
        if not (data.startswith(b"ID3") or len(data) > 2 and data[0] == 255 and data[1] & 224 == 224):
            raise ValueError("Invalid MP3 audio signature.")
    else:
        raise ValueError("Only MP3 and PCM WAV audio are supported.")


def tts_configuration():
    """Expose non-secret readiness for the selected provider, never its key."""
    provider = os.environ.get("TTS_PROVIDER", "").strip().lower()
    if provider == "gemini":
        configured = bool(os.environ.get("GEMINI_API_KEY"))
        voice = os.environ.get("GEMINI_TTS_VOICE", "Kore")
    elif provider == "azure":
        configured = bool(os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"))
        voice = os.environ.get("AZURE_SPEECH_VOICE", "my-MM-NilarNeural")
    else:
        configured, voice = False, ""
    return {"tts_provider": provider, "tts_configured": configured, "voice": voice,
            "tts_enabled": os.environ.get("PYONPYIN_TTS_ENABLED", "").lower() == "true"}


class GeminiSpeechTTS:
    """Gemini Interactions TTS API; shares the story-generation API key."""

    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
        self.voice = os.environ.get("GEMINI_TTS_VOICE", "Kore")
        if not self.api_key:
            raise AudioUnavailable("Set GEMINI_API_KEY before using Gemini speech.")
        # Lite model တွင် Burmese မပါသဖြင့် လက်ရှိစစ်ထားသော full TTS model ကိုသာ သုံးသည်။
        if self.model != "gemini-3.8-flash-tts":
            raise AudioUnavailable("Use GEMINI_TTS_MODEL=gemini-3.8-flash-tts for this Burmese adapter.")
        if not re.fullmatch(r"[A-Za-z]{1,40}", self.voice):
            raise AudioUnavailable("Choose a prebuilt Gemini voice, for example Kore.")

    def _synthesize_chunk(self, text):
        body = {
            "model": self.model, "store": False,
            "input": [{"type": "user_input", "content": [{
                "type": "text", "text": text,
                "annotations": [{"type": "speech_metadata",
                                 "style": "Warm, clear Burmese narration at a natural reading pace."}],
            }]}],
            "response_format": {"type": "audio", "mime_type": "audio/wav", "sample_rate": 24000},
            "generation_config": {"speech_config": [{"voice": self.voice}]},
        }
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
            method="POST",
        )
        # Timeout/HTTP error ကို အလိုအလျောက် ထပ်မခေါ်ပါ။ Usage စစ်ပြီးမှ လူက retry ရွေးရသည်။
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                maximum = 4 * ((MAX_AUDIO_BYTES + 2) // 3) + 65_536
                raw = response.read(maximum + 1)
                if len(raw) > maximum:
                    raise AudioUnavailable("Gemini audio response exceeds the size limit.")
            payload = json.loads(raw)
            if payload.get("status", "completed") != "completed":
                raise AudioUnavailable("Gemini speech did not complete; inspect usage before retrying.")
            audio_blocks = [block for step in payload.get("steps", [])
                            if step.get("type") == "model_output"
                            for block in step.get("content", []) if block.get("type") == "audio"]
            if not audio_blocks:
                raise AudioUnavailable("Gemini returned no speech audio; check model access and content policy.")
            data = base64.b64decode(audio_blocks[-1]["data"], validate=True)
            validate_audio(data, ".wav")
            return data
        except urllib.error.HTTPError as exc:
            exc.close()
            raise AudioUnavailable(f"Gemini speech returned HTTP {exc.code}; check API access and quota.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AudioUnavailable("Gemini speech request failed; inspect usage before retrying.") from exc
        except (ValueError, KeyError, TypeError, AttributeError, binascii.Error) as exc:
            raise AudioUnavailable("Gemini returned invalid speech audio.") from exc

    def synthesize_bytes(self, text):
        if not isinstance(text, str) or not text.strip() or len(text) > 20_000:
            raise ValueError("Narration requires 1–20,000 story characters.")
        output = io.BytesIO()
        with wave.open(output, "wb") as combined:
            combined.setnchannels(1)
            combined.setsampwidth(2)
            combined.setframerate(24000)
            # စာသားကို transcript အဖြစ်သာ ပို့ပြီး အသံညွှန်ကြားချက်ကို metadata သီးခြားထားသည်။
            for start in range(0, len(text), 1_000):
                data = self._synthesize_chunk(text[start:start + 1_000])
                with wave.open(io.BytesIO(data), "rb") as audio:
                    current = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
                    if current != (1, 2, 24000) or audio.getcomptype() != "NONE":
                        raise AudioUnavailable("Gemini returned an unsupported speech format.")
                    frames = audio.readframes(audio.getnframes())
                    if not frames or len(frames) != audio.getnframes() * 2:
                        raise AudioUnavailable("Gemini returned incomplete speech audio.")
                    combined.writeframes(frames)
                if output.tell() > MAX_AUDIO_BYTES:
                    raise AudioUnavailable("Combined narration exceeds 25 MiB.")
        return output.getvalue()


class AzureSpeechTTS:
    """Bounded SSML requests; output always needs a human listening review."""

    def __init__(self):
        self.api_key = os.environ.get("AZURE_SPEECH_KEY", "")
        self.region = os.environ.get("AZURE_SPEECH_REGION", "")
        self.voice = os.environ.get("AZURE_SPEECH_VOICE", "my-MM-NilarNeural")
        if not self.api_key or not re.fullmatch(r"[a-z0-9-]{2,40}", self.region):
            raise AudioUnavailable("Set AZURE_SPEECH_KEY and AZURE_SPEECH_REGION.")
        if not re.fullmatch(r"my-MM-[A-Za-z]+Neural", self.voice):
            raise AudioUnavailable("Choose an explicit Burmese my-MM neural voice.")
        self.base_url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices"

    def _request(self, url, body=None):
        request = urllib.request.Request(url, data=body, headers={
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
            "User-Agent": "PyonPyin",
        })
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                data = response.read(MAX_AUDIO_BYTES + 1)
                if len(data) > MAX_AUDIO_BYTES:
                    raise AudioUnavailable("Speech response exceeded the audio size limit.")
                return data
        except urllib.error.HTTPError as exc:
            exc.close()
            raise AudioUnavailable(f"Azure Speech returned HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise AudioUnavailable("Speech request failed; review before retrying.") from exc

    def synthesize_bytes(self, text):
        import json
        if not text.strip() or len(text) > 20_000:
            raise ValueError("Narration requires 1–20,000 story characters.")
        # Region တွင် အသံရှိကြောင်း အရင်စစ်ပြီးမှ bill ဖြစ်နိုင်သော synthesis ကို ခေါ်သည်။
        voices = json.loads(self._request(self.base_url + "/voices/list"))
        if not any(v.get("ShortName") == self.voice and v.get("Locale") == "my-MM" for v in voices):
            raise AudioUnavailable("Configured Burmese voice is unavailable in this region.")
        output = io.BytesIO()
        parameters = None
        with wave.open(output, "wb") as combined:
            combined.setnchannels(1)
            combined.setsampwidth(2)
            combined.setframerate(24000)
            # ရှည်သောပုံပြင်ကို အပိုင်းတိုများခွဲပြီး PCM frame များ ပြန်ဆက်သည်။
            for start in range(0, len(text), 1_000):
                chunk = text[start:start + 1_000]
                ssml = (f'<speak version="1.0" xml:lang="my-MM"><voice name="{self.voice}">'
                        f'{escape(chunk)}</voice></speak>').encode("utf-8")
                data = self._request(self.base_url + "/v1", ssml)
                validate_audio(data, ".wav")
                with wave.open(io.BytesIO(data), "rb") as audio:
                    current = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate())
                    if audio.getnframes() / audio.getframerate() >= 590:
                        raise AudioUnavailable("Speech may be truncated; use shorter narration text.")
                    if parameters is None:
                        parameters = current
                        combined.setnchannels(current[0])
                        combined.setsampwidth(current[1])
                        combined.setframerate(current[2])
                    elif current != parameters:
                        raise AudioUnavailable("Speech chunks returned inconsistent PCM formats.")
                    combined.writeframes(audio.readframes(audio.getnframes()))
                if output.tell() > MAX_AUDIO_BYTES:
                    raise AudioUnavailable("Combined narration exceeds 25 MiB.")
        return output.getvalue()


class GoogleCloudTTS:
    """Google Cloud TTS adapter requiring a verified my-MM voice and API key."""

    def __init__(self, api_key=None, voice=None, output_dir=None):
        self.api_key = api_key or os.environ.get("GOOGLE_TTS_API_KEY")
        self.voice = voice or os.environ.get("GOOGLE_TTS_VOICE")
        self.output_dir = output_dir or os.environ.get("AUDIO_OUTPUT_DIR", "data/audio")
        if not self.api_key or not self.voice:
            raise AudioUnavailable(
                "Set GOOGLE_TTS_API_KEY and GOOGLE_TTS_VOICE to a verified my-MM voice. "
                "Burmese voice availability must be verified before enabling narration."
            )
        if not self.voice.lower().startswith("my-mm-"):
            raise ValueError("Only an explicitly configured my-MM voice is accepted.")

    def synthesize(self, text, filename):
        # လက်ရှိ placeholder ဖြစ်သည်။ Voice အတည်ပြုမှုနှင့် adapter မပြီးသေးလို့ အသံဖိုင်မထုတ်ဘဲ error ပေးသည်။
        if not text.strip():
            raise ValueError("Narration text cannot be empty.")
        raise AudioUnavailable(
            "The Google Cloud TTS adapter is intentionally disabled until a current "
            "my-MM voice is confirmed in the official voice catalogue and tested "
            "with a native Myanmar-language reviewer."
        )


def configured_provider():
    # Environment ထဲက provider ကိုရွေးသည်။ မသတ်မှတ်ထားလျှင် အသံဝန်ဆောင်မှု မဖွင့်ပါ။
    provider = os.environ.get("TTS_PROVIDER", "").strip().lower()
    if not provider:
        return None
    if provider == "google-cloud":
        return GoogleCloudTTS()
    if provider == "azure":
        return AzureSpeechTTS()
    if provider == "gemini":
        return GeminiSpeechTTS()
    raise AudioUnavailable(f"Unsupported TTS_PROVIDER: {provider}")
