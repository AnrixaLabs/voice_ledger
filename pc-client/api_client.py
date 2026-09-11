"""
Talks to the same server the Android app talks to - see
server/app/main.py. Kept as plain functions (not a class) since a
desktop settings screen is the only thing that needs a base URL, and
it can just be threaded through.
"""
from pathlib import Path
from typing import Any

import requests


class ApiError(Exception):
    pass


def _url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def pair_start(base_url: str) -> dict:
    resp = requests.post(_url(base_url, "/pair/start"), timeout=10)
    _raise_for_status(resp)
    return resp.json()


def pair_complete(base_url: str, pairing_code: str, label: str, public_key_pem: str) -> dict:
    resp = requests.post(
        _url(base_url, "/pair/complete"),
        json={"pairing_code": pairing_code, "label": label, "public_key_pem": public_key_pem},
        timeout=10,
    )
    _raise_for_status(resp)
    return resp.json()


def speech_to_text(base_url: str, wav_path: Path) -> str:
    with open(wav_path, "rb") as f:
        resp = requests.post(
            _url(base_url, "/stt"), files={"audio": (wav_path.name, f, "audio/wav")}, timeout=60
        )
    _raise_for_status(resp)
    return resp.json()["transcript"]


def guided_field(base_url: str, field: str, transcript: str) -> dict:
    resp = requests.post(
        _url(base_url, "/nlu/guided-field"),
        params={"field": field, "transcript": transcript},
        timeout=10,
    )
    _raise_for_status(resp)
    return resp.json()


def submit_transaction(base_url: str, device_id: str, payload_json: str, signature_b64: str) -> dict:
    resp = requests.post(
        _url(base_url, "/transactions"),
        json={"device_id": device_id, "payload_json": payload_json, "signature_b64": signature_b64},
        timeout=10,
    )
    _raise_for_status(resp)
    return resp.json()


def list_transactions(base_url: str) -> list[dict]:
    resp = requests.get(_url(base_url, "/transactions"), timeout=10)
    _raise_for_status(resp)
    return resp.json()


def fetch_tts(base_url: str, text: str) -> bytes:
    resp = requests.get(_url(base_url, "/tts"), params={"text": text}, timeout=30)
    _raise_for_status(resp)
    return resp.content


def _raise_for_status(resp: requests.Response) -> None:
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:  # noqa: BLE001
            detail = resp.text
        raise ApiError(f"{resp.status_code}: {detail}")
