"""
TLS for a server with no public domain and no CA.

There's no certificate authority that will issue a "real" cert for a
LAN IP address, so this generates a long-lived self-signed one on
first run and the trust model is TOFU (trust-on-first-use), the same
way SSH host keys work: the fingerprint is printed to the server's
own console, and each client is expected to compare that against what
it sees on first connect - during pairing, since that's already the
moment a human is standing at both the server and the new device. See
docs/SECURITY.md ("Transport security") for the full writeup.

Rotating this certificate invalidates every client's pin, so it's
deliberately long-lived (10 years) rather than auto-renewed - treat
regenerating it as a "re-pair every device" event, not a routine task.
"""
import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def ensure_certificate(cert_path: Path, key_path: Path) -> tuple[Path, Path, str]:
    """Generates cert_path/key_path if they don't already exist. Always
    returns (cert_path, key_path, sha256_fingerprint_hex)."""
    if not cert_path.exists() or not key_path.exists():
        _generate(cert_path, key_path)
    fingerprint = _fingerprint(cert_path)
    return cert_path, key_path, fingerprint


def _generate(cert_path: Path, key_path: Path) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = ec.generate_private_key(ec.SECP256R1())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "voice-ledger-local-server"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1")),
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    key_path.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    # Private key readable by the server process only.
    key_path.chmod(0o600)


def _fingerprint(cert_path: Path) -> str:
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    digest = cert.fingerprint(hashes.SHA256())
    return ":".join(f"{b:02X}" for b in digest)
