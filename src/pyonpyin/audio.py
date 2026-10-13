"""Configurable TTS adapter; no unverified Burmese voice is assumed."""

import os
import urllib.error
import urllib.request


class AudioUnavailable(RuntimeError):
    pass


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
        if not text.strip():
            raise ValueError("Narration text cannot be empty.")
        raise AudioUnavailable(
            "The Google Cloud TTS adapter is intentionally disabled until a current "
            "my-MM voice is confirmed in the official voice catalogue and tested "
            "with a native Myanmar-language reviewer."
        )


def configured_provider():
    provider = os.environ.get("TTS_PROVIDER", "").strip().lower()
    if not provider:
        return None
    if provider == "google-cloud":
        return GoogleCloudTTS()
    raise AudioUnavailable(f"Unsupported TTS_PROVIDER: {provider}")
