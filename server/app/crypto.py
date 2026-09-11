"""
Security model in one paragraph:

A fingerprint (or Windows Hello) prompt never travels over the network
and the server never sees biometric data. Instead, at pairing time each
device generates an ECDSA (P-256) key pair inside its own secure
hardware (Android Keystore / Windows Hello + TPM) and registers only
the *public* key here. The private key is configured so the OS will
not use it to sign anything without a fresh biometric check. So when a
user confirms a ledger entry with their fingerprint, what actually
happens is: the OS unlocks the private key for one signing operation,
the client signs the canonical JSON of the entry, and sends the
payload + signature. This server's only job is to verify that
signature against the registered public key before writing the row.
If the signature doesn't match, the entry never touches the database.
"""
import json
import secrets
import string
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.exceptions import InvalidSignature


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic JSON so client and server hash the exact same bytes."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def generate_pairing_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    # Exclude visually ambiguous characters for a code a human reads off a screen.
    alphabet = "".join(c for c in alphabet if c not in "0O1I")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def verify_signature(public_key_pem: str, payload_json: str, signature_b64: str) -> bool:
    """Verifies against whichever key type the device registered at
    pairing time. The Android client's Keystore key is ECDSA
    (secp256r1/SHA-256) - see BiometricSigner.kt. The Windows client's
    Windows Hello key credential is always RSA-2048, signed with
    PKCS#1 v1.5/SHA-256 - see pc-client/biometric_windows.py and
    https://learn.microsoft.com/uwp/api/windows.security.credentials.keycredentialmanager.requestcreateasync
    ("generates a new RSA 2048-bit key credential"). Both are legitimate
    hardware/TPM-backed, biometric-gated keys; the server just needs to
    know which flavor of math to check.
    """
    import base64

    try:
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        signature = base64.b64decode(signature_b64)
        message = payload_json.encode("utf-8")

        if isinstance(public_key, EllipticCurvePublicKey):
            public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        elif isinstance(public_key, RSAPublicKey):
            public_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        else:
            return False
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
