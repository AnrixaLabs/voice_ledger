"""
Data model.

Device: a phone or PC that has completed pairing. We store its public
key only — never anything biometric, never a private key.

Transaction: one confirmed ledger entry. `payload_json` is the exact
canonical bytes the client signed; `signature` is verified against the
owning device's public key before a row is ever written (see auth.py
and main.py). Because payload_json is stored verbatim, any later
dispute can be re-verified byte-for-byte against the signature.
"""
from datetime import datetime, date, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from pydantic import BaseModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Device(SQLModel, table=True):
    id: str = Field(primary_key=True)  # uuid4, generated at pairing time
    label: str  # e.g. "Levon's Galaxy A55", "Office PC"
    public_key_pem: str
    paired_at: datetime = Field(default_factory=_utcnow)
    revoked: bool = False


class Transaction(SQLModel, table=True):
    id: str = Field(primary_key=True)  # uuid4, chosen by the client
    device_id: str = Field(foreign_key="device.id")

    counterparty_name: str
    place: Optional[str] = None
    amount_paid: Optional[float] = None
    amount_paid_currency: Optional[str] = None
    amount_due: Optional[float] = None
    amount_due_currency: Optional[str] = None
    due_date: Optional[date] = None
    transaction_date: Optional[date] = None

    raw_transcript: str  # what was actually heard, for audit
    payload_json: str  # canonical JSON that was signed
    signature_b64: str

    created_at: datetime = Field(default_factory=_utcnow)


# ---- API schemas (not tables) ----

class PairStartResponse(BaseModel):
    pairing_code: str
    expires_in: int


class PairCompleteRequest(BaseModel):
    pairing_code: str
    label: str
    public_key_pem: str


class PairCompleteResponse(BaseModel):
    device_id: str


class TransactionIn(BaseModel):
    device_id: str
    payload_json: str  # canonical JSON, see crypto.canonical_json
    signature_b64: str


class TransactionOut(BaseModel):
    id: str
    counterparty_name: str
    place: Optional[str]
    amount_paid: Optional[float]
    amount_paid_currency: Optional[str]
    amount_due: Optional[float]
    amount_due_currency: Optional[str]
    due_date: Optional[date]
    transaction_date: Optional[date]
    created_at: datetime
