import json
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from . import auth, stt, tts
from .config import settings
from .crypto import verify_signature
from .db import get_session, init_db
from .models import (
    Device, PairCompleteRequest, PairCompleteResponse, PairStartResponse,
    Transaction, TransactionIn, TransactionOut,
)
from .nlu.extractor import extract_guided_field


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.service_name, lifespan=_lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.service_name}


# ---------------------------------------------------------------- pairing

@app.post("/pair/start", response_model=PairStartResponse)
def pair_start() -> PairStartResponse:
    """Call this on the server/PC console. Show the returned code to the
    person pairing a new phone or PC client."""
    code, ttl = auth.start_pairing()
    return PairStartResponse(pairing_code=code, expires_in=ttl)


@app.post("/pair/complete", response_model=PairCompleteResponse)
def pair_complete(
    req: PairCompleteRequest, session: Session = Depends(get_session)
) -> PairCompleteResponse:
    """Call this from the new client with the code the human just typed
    in, plus the public key half of the key pair it generated locally."""
    if not auth.consume_pairing_code(req.pairing_code):
        raise HTTPException(400, "Invalid or expired pairing code.")

    device = Device(id=str(uuid.uuid4()), label=req.label, public_key_pem=req.public_key_pem)
    session.add(device)
    session.commit()
    return PairCompleteResponse(device_id=device.id)


# ------------------------------------------------------------ speech I/O

@app.post("/stt")
async def speech_to_text(audio: UploadFile) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    try:
        transcript = stt.transcribe(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return {"transcript": transcript}


@app.post("/nlu/guided-field")
def nlu_guided_field(field: str, transcript: str) -> dict:
    try:
        return extract_guided_field(field, transcript)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, str(exc)) from exc


@app.get("/tts")
def text_to_speech(text: str) -> FileResponse:
    try:
        wav_path = tts.synthesize(text)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    return FileResponse(wav_path, media_type="audio/wav")


# -------------------------------------------------------- signed entries

@app.post("/transactions", response_model=TransactionOut)
def submit_transaction(
    body: TransactionIn, session: Session = Depends(get_session)
) -> TransactionOut:
    device = session.get(Device, body.device_id)
    if device is None or device.revoked:
        raise HTTPException(403, "Unknown or revoked device.")

    if not verify_signature(device.public_key_pem, body.payload_json, body.signature_b64):
        # This is the whole point of the biometric step: if the
        # signature doesn't check out, nothing is written.
        raise HTTPException(403, "Signature verification failed.")

    # Note on integrity: we deliberately do NOT re-serialize `payload`
    # and compare it to body.payload_json for exact byte equality. The
    # signature already covers the literal bytes of body.payload_json
    # as sent - that's what verify_signature just checked - so the
    # client cannot sign one payload and submit a different one; JSON
    # formatting differences between the Kotlin/Python/Swift clients
    # (key order, float formatting, whitespace) are harmless as long
    # as each client signs exactly the bytes it transmits.
    payload = json.loads(body.payload_json)

    def _parse_date(value: str | None):
        return date.fromisoformat(value) if value else None

    txn = Transaction(
        id=payload.get("id") or str(uuid.uuid4()),
        device_id=device.id,
        counterparty_name=payload["counterparty_name"],
        place=payload.get("place"),
        amount_paid=payload.get("amount_paid"),
        amount_paid_currency=payload.get("amount_paid_currency"),
        amount_due=payload.get("amount_due"),
        amount_due_currency=payload.get("amount_due_currency"),
        due_date=_parse_date(payload.get("due_date")),
        transaction_date=_parse_date(payload.get("transaction_date")),
        raw_transcript=payload.get("raw_transcript", ""),
        payload_json=body.payload_json,
        signature_b64=body.signature_b64,
    )
    session.add(txn)
    session.commit()
    session.refresh(txn)
    return TransactionOut(**txn.model_dump())


@app.get("/transactions", response_model=list[TransactionOut])
def list_transactions(session: Session = Depends(get_session)) -> list[TransactionOut]:
    rows = session.exec(select(Transaction).order_by(Transaction.created_at.desc())).all()
    return [TransactionOut(**r.model_dump()) for r in rows]
