"""
Central configuration for the voice-ledger local server.

Everything here is meant to be overridden via a .env file that never
leaves the machine it runs on. See .env.example.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Network ---
    # Bind to the LAN interface only. 0.0.0.0 is fine on a machine that
    # sits behind a home/office router with no port forwarding; do not
    # expose this port to the public internet.
    host: str = "0.0.0.0"
    port: int = 8420
    service_name: str = "Anrixa Voice Ledger"  # advertised over mDNS

    # --- Storage ---
    data_dir: Path = Path("./data")
    db_path: Path = Path("./data/ledger.db")

    # --- Pairing / security ---
    # Pairing codes are short-lived, single-use, and only ever needed
    # once per device. See app/auth.py.
    pairing_code_ttl_seconds: int = 600

    # --- Speech-to-text ---
    # "local" uses faster-whisper on this machine (offline, private).
    # "azure" calls Azure Speech (requires internet + azure_speech_key).
    stt_provider: str = "local"
    stt_model_size: str = "medium"  # tiny/base/small/medium/large-v3
    # Optional: point at a fine-tuned Armenian checkpoint instead of the
    # stock multilingual model, e.g. a CTranslate2 export of a model
    # such as Chillarmo/checkpoint_9971 (morpheme-aware Whisper-tiny
    # trained on Common Voice hy). Leave blank to use stt_model_size.
    stt_model_path: str = ""

    # --- Text-to-speech (confirmation read-back) ---
    # "azure" uses Azure Neural voices hy-AM-AnahitNeural / hy-AM-HaykNeural,
    # which is the recommended "nice" Armenian voice as of 2026.
    # "none" disables spoken confirmation (screen text only).
    tts_provider: str = "azure"
    tts_voice: str = "hy-AM-AnahitNeural"
    azure_speech_key: str = ""
    azure_speech_region: str = ""

    # --- Free-form extraction mode (optional) ---
    # Guided mode (field-by-field) never needs this. Free-form mode
    # (one long utterance) uses Claude to pull structured fields out
    # of the transcript when an internet connection is available.
    anthropic_api_key: str = ""
    freeform_model: str = "claude-sonnet-4-6"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
