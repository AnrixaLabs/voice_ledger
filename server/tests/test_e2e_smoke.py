"""
Simulates what an Android/PC client actually does, end to end, against
the real FastAPI app: pair a device, generate an EC key pair "in
hardware" (here: in-process, standing in for Keystore/Windows Hello),
sign a canonical transaction payload, and confirm the server accepts
a correctly-signed entry and rejects a tampered one.
"""
import base64
import os
import sys
import tempfile
from pathlib import Path

os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["DB_PATH"] = str(Path(os.environ["DATA_DIR"]) / "test.db")
os.environ["TTS_PROVIDER"] = "none"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from app.main import app
from app.crypto import canonical_json

# Context-manager form so FastAPI's lifespan (init_db) actually runs.
client = TestClient(app)
client.__enter__()


def _sign(private_key, payload_json: str) -> str:
    sig = private_key.sign(payload_json.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(sig).decode("ascii")


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_full_pairing_and_signed_submission_roundtrip():
    # 1. Server-side: start pairing, get a code.
    start = client.post("/pair/start").json()
    code = start["pairing_code"]
    assert len(code) == 8

    # 2. Client-side: generate a key pair "in secure hardware".
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")

    complete = client.post(
        "/pair/complete",
        json={"pairing_code": code, "label": "Test Galaxy A55", "public_key_pem": public_pem},
    )
    assert complete.status_code == 200
    device_id = complete.json()["device_id"]

    # A used-up code must not work twice.
    replay = client.post(
        "/pair/complete",
        json={"pairing_code": code, "label": "Replay", "public_key_pem": public_pem},
    )
    assert replay.status_code == 400

    # 3. Client-side: build the canonical payload for a confirmed entry
    #    and sign it (the step gated by the fingerprint prompt).
    payload = {
        "id": "11111111-1111-1111-1111-111111111111",
        "counterparty_name": "Armen Petrosyan",
        "place": "Yerevan",
        "amount_paid": 50000.0,
        "amount_paid_currency": "AMD",
        "amount_due": 20000.0,
        "amount_due_currency": "AMD",
        "due_date": "2026-10-01",
        "transaction_date": "2026-09-11",
        "raw_transcript": "Armen Petrosyan, Yerevan, paid fifty thousand dram, owes twenty thousand, due October first",
    }
    payload_json = canonical_json(payload)
    signature = _sign(private_key, payload_json)

    submit = client.post(
        "/transactions",
        json={"device_id": device_id, "payload_json": payload_json, "signature_b64": signature},
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["counterparty_name"] == "Armen Petrosyan"
    assert body["amount_paid"] == 50000.0
    assert body["due_date"] == "2026-10-01"

    # 4. It shows up in the ledger.
    listing = client.get("/transactions").json()
    assert any(t["id"] == payload["id"] for t in listing)


def test_tampered_payload_with_valid_signature_for_original_is_rejected():
    """A malicious client can't sign payload A and submit payload B."""
    start = client.post("/pair/start").json()
    code = start["pairing_code"]

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")
    device_id = client.post(
        "/pair/complete",
        json={"pairing_code": code, "label": "Attacker device", "public_key_pem": public_pem},
    ).json()["device_id"]

    original = canonical_json({"id": "x", "counterparty_name": "Armen", "amount_paid": 1000.0})
    signature = _sign(private_key, original)

    tampered = canonical_json({"id": "x", "counterparty_name": "Armen", "amount_paid": 9_000_000.0})
    resp = client.post(
        "/transactions",
        json={"device_id": device_id, "payload_json": tampered, "signature_b64": signature},
    )
    assert resp.status_code == 403


def test_unknown_device_is_rejected():
    resp = client.post(
        "/transactions",
        json={"device_id": "does-not-exist", "payload_json": "{}", "signature_b64": "AA=="},
    )
    assert resp.status_code == 403


def test_rsa_device_key_roundtrip():
    """The PC client uses a Windows Hello RSA-2048 key credential
    instead of Android's EC key - the server must verify both."""
    start = client.post("/pair/start").json()
    code = start["pairing_code"]

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("utf-8")
    device_id = client.post(
        "/pair/complete",
        json={"pairing_code": code, "label": "Office PC", "public_key_pem": public_pem},
    ).json()["device_id"]

    payload = canonical_json({"id": "rsa-1", "counterparty_name": "Anahit", "amount_paid": 15000.0})
    signature = base64.b64encode(
        private_key.sign(payload.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")

    resp = client.post(
        "/transactions",
        json={"device_id": device_id, "payload_json": payload, "signature_b64": signature},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["counterparty_name"] == "Anahit"
