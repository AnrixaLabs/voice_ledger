"""
Pairing flow, in three steps:

1. On the server machine (or its PC client, which sits on the same
   LAN), someone starts pairing. The server generates a short code
   and shows it on screen - this is the "is this really my phone"
   check, since anyone who can read the screen is assumed to be
   physically present at the server.
2. The phone (or the other client) is pointed at the server's address,
   enters the code, and sends the public half of a key pair it just
   generated in its secure hardware (Android Keystore / Windows Hello).
3. The server stores that public key against a new device id and the
   code is discarded. From then on, every ledger entry from that
   device must carry a signature verifiable against this key.

Codes live in memory only (not the database) and expire quickly -
there's no reason to persist a value that's only ever useful for the
few seconds a human is typing it in.
"""
import time

from .config import settings
from .crypto import generate_pairing_code

_pending: dict[str, float] = {}  # code -> expiry unix timestamp


def start_pairing() -> tuple[str, int]:
    code = generate_pairing_code()
    _pending[code] = time.time() + settings.pairing_code_ttl_seconds
    return code, settings.pairing_code_ttl_seconds


def consume_pairing_code(code: str) -> bool:
    expiry = _pending.pop(code, None)
    return expiry is not None and expiry >= time.time()
