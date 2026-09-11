"""
Speech-to-text.

`local` (default): faster-whisper running on this machine's CPU/GPU.
Fully offline and private - the recommended mode for financial voice
notes. First run downloads the model weights once (needs internet
that one time); after that it works with no network at all.

For best Armenian accuracy, consider pointing stt_model_path at a
fine-tuned Armenian checkpoint (e.g. a CTranslate2 export of a
Common-Voice-trained Armenian Whisper model) instead of the stock
multilingual `medium` model - stock Whisper's Armenian word-error
rate is noticeably higher than its high-resource languages.

`azure`: calls Azure Speech's REST API. Needs internet + an Azure key,
but requires no local model download and no GPU.

The heavy model is lazy-loaded on first use, not at import time, so
importing this module (e.g. for tests) stays fast.
"""
from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def _local_model():
    from faster_whisper import WhisperModel

    model_ref = settings.stt_model_path or settings.stt_model_size
    return WhisperModel(model_ref, device="auto", compute_type="auto")


def transcribe(audio_path: str, language: str = "hy") -> str:
    if settings.stt_provider == "local":
        model = _local_model()
        segments, _info = model.transcribe(audio_path, language=language, vad_filter=True)
        return " ".join(seg.text.strip() for seg in segments).strip()

    if settings.stt_provider == "azure":
        return _transcribe_azure(audio_path, language=language)

    raise ValueError(f"Unknown stt_provider: {settings.stt_provider}")


def _transcribe_azure(audio_path: str, language: str) -> str:
    import requests

    if not settings.azure_speech_key or not settings.azure_speech_region:
        raise RuntimeError("Azure STT needs azure_speech_key and azure_speech_region set.")

    url = (
        f"https://{settings.azure_speech_region}.stt.speech.microsoft.com"
        f"/speech/recognition/conversation/cognitiveservices/v1"
        f"?language={language}-AM"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": settings.azure_speech_key,
        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
    }
    with open(audio_path, "rb") as f:
        resp = requests.post(url, headers=headers, data=f, timeout=30)
    resp.raise_for_status()
    return resp.json().get("DisplayText", "")
