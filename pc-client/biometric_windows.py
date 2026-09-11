"""
Windows Hello signing, via the same Microsoft "Passport"/KeyCredentialManager
API used for password-less sign-in. This is the Windows analog of
BiometricSigner.kt on Android: the private key is generated inside the
TPM and never leaves it; RequestSignAsync triggers the Windows Hello
prompt (PIN, fingerprint, or face, whatever's enrolled) and only
returns a signature if that check succeeds.

Confirmed from Microsoft's own docs (see comment in
server/app/crypto.py for the link): RequestCreateAsync always
generates an RSA-2048 key, and the matching verification example
uses PKCS#1 v1.5 padding with SHA-256 - that's what the server's
verify_signature() expects from an RSA device key.

Needs: Windows 10/11 with Windows Hello configured (PIN at minimum;
fingerprint reader for the "actual fingerprint" experience this app
is going for) and the `winsdk` package. This file only runs on
Windows - see main.py for how it's imported conditionally.
"""
import asyncio
import base64

from winsdk.windows.security.credentials import (
    KeyCredentialManager,
    KeyCredentialCreationOption,
    KeyCredentialStatus,
)
from winsdk.windows.security.cryptography.core import CryptographicPublicKeyBlobType
from winsdk.windows.storage.streams import DataWriter, DataReader, UnicodeEncoding

_ACCOUNT_ID = "com.anrixa.voiceledger"


class BiometricUnavailable(Exception):
    pass


def _str_to_buffer(text: str):
    writer = DataWriter()
    writer.unicode_encoding = UnicodeEncoding.UTF8
    writer.write_string(text)
    return writer.detach_buffer()


def _buffer_to_bytes(buf) -> bytes:
    reader = DataReader.from_buffer(buf)
    out = bytearray(buf.length)
    reader.read_bytes(out)
    return bytes(out)


async def _ensure_credential():
    supported = await KeyCredentialManager.is_supported_async()
    if not supported:
        raise BiometricUnavailable(
            "Windows Hello isn't set up on this PC. Set up a PIN or "
            "fingerprint under Settings > Accounts > Sign-in options, "
            "then try again."
        )

    open_result = await KeyCredentialManager.open_async(_ACCOUNT_ID)
    if open_result.status == KeyCredentialStatus.SUCCESS:
        return open_result.credential

    create_result = await KeyCredentialManager.request_create_async(
        _ACCOUNT_ID, KeyCredentialCreationOption.FAIL_IF_EXISTS
    )
    if create_result.status != KeyCredentialStatus.SUCCESS:
        raise BiometricUnavailable(f"Could not create a Windows Hello key: {create_result.status}")
    return create_result.credential


async def _get_public_key_pem_async() -> str:
    credential = await _ensure_credential()
    # X509SubjectPublicKeyInfo = the same DER SubjectPublicKeyInfo format
    # the Android client's PublicKey.getEncoded() produces, so the
    # server's serialization.load_pem_public_key() handles either
    # without caring which platform it came from.
    key_buf = await credential.retrieve_public_key_async(
        CryptographicPublicKeyBlobType.X509_SUBJECT_PUBLIC_KEY_INFO
    )
    der = _buffer_to_bytes(key_buf)
    b64 = base64.b64encode(der).decode("ascii")
    lines = "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64))
    return f"-----BEGIN PUBLIC KEY-----\n{lines}\n-----END PUBLIC KEY-----\n"


async def _sign_async(canonical_payload_json: str) -> str:
    credential = await _ensure_credential()
    # This line is what actually pops the Windows Hello prompt.
    result = await credential.request_sign_async(_str_to_buffer(canonical_payload_json))
    if result.status == KeyCredentialStatus.USER_CANCELED:
        raise BiometricUnavailable("Cancelled.")
    if result.status != KeyCredentialStatus.SUCCESS:
        raise BiometricUnavailable(f"Windows Hello confirmation failed: {result.status}")
    return base64.b64encode(_buffer_to_bytes(result.result)).decode("ascii")


# ---- sync wrappers: PySide6 code calls these from a worker thread, ----
# ---- never the Qt UI thread (each spins up its own asyncio loop). -----

def get_public_key_pem() -> str:
    return asyncio.run(_get_public_key_pem_async())


def sign_with_windows_hello(canonical_payload_json: str) -> str:
    return asyncio.run(_sign_async(canonical_payload_json))
