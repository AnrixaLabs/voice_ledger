"""
Text-to-speech for the spoken confirmation read-back.

Armenian isn't in most phones' on-device TTS engine, so this is
server-side by design: the client just plays back an audio file the
server hands it. As of this writing, Azure Speech's neural voices
hy-AM-AnahitNeural (female) and hy-AM-HaykNeural (male) are the
strongest natural-sounding Armenian option, which is why they're the
default here - verify current voice quality/pricing against Azure's
docs before shipping, since providers update these regularly.

Confirmation phrases repeat a lot ("You said <name>, paid <amount>
<currency>...") with only the field values changing, so results are
cached to disk by a hash of the exact text - most of a sentence's
audio ends up reused across entries.
"""
import hashlib
from pathlib import Path

from .config import settings

_CACHE_DIR = settings.data_dir / "tts_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def synthesize(text: str) -> Path:
    """Returns a path to a .wav file with `text` spoken aloud. Cached."""
    if settings.tts_provider == "none":
        raise RuntimeError("TTS is disabled (tts_provider=none).")

    key = hashlib.sha256(f"{settings.tts_voice}:{text}".encode("utf-8")).hexdigest()[:24]
    cached = _CACHE_DIR / f"{key}.wav"
    if cached.exists():
        return cached

    if settings.tts_provider == "azure":
        audio_bytes = _synthesize_azure(text)
    else:
        raise ValueError(f"Unknown tts_provider: {settings.tts_provider}")

    cached.write_bytes(audio_bytes)
    return cached


def _synthesize_azure(text: str) -> bytes:
    import requests

    if not settings.azure_speech_key or not settings.azure_speech_region:
        raise RuntimeError("Azure TTS needs azure_speech_key and azure_speech_region set.")

    ssml = (
        '<speak version="1.0" xml:lang="hy-AM">'
        f'<voice name="{settings.tts_voice}">{_xml_escape(text)}</voice>'
        "</speak>"
    )
    url = f"https://{settings.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
    }
    resp = requests.post(url, headers=headers, data=ssml.encode("utf-8"), timeout=30)
    resp.raise_for_status()
    return resp.content


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        .replace('"', "&quot;").replace("'", "&apos;")
    )
