# Security model

## What "confirmed by biometric signature" actually means here

Not: "a fingerprint scan gets sent to a server and checked." That
would mean biometric data crossing the network, which this design
specifically avoids.

What actually happens: at pairing time, each device generates a key
pair inside its own secure hardware — Android Keystore, or a Windows
Hello key credential backed by the TPM. Only the *public* half is
ever sent anywhere (to the server, during pairing). The private key
is configured so the OS will not use it to produce a signature
without a fresh, successful biometric check immediately beforehand —
`setUserAuthenticationRequired` + `setInvalidatedByBiometricEnrollment`
on Android, the Windows Hello gesture built into
`KeyCredential.RequestSignAsync` on Windows.

So when someone taps "confirm" and scans their fingerprint: the OS
verifies the fingerprint locally, and *only if that succeeds* does it
hand back a signature over the transaction data. That signature, plus
the plain transaction data, is what reaches the server. The server's
only job is checking that signature against the public key it stored
for that device at pairing time (`server/app/crypto.py:verify_signature`,
tested in `server/tests/test_e2e_smoke.py`). If it doesn't match, the
entry is never written — this is in the test suite, including the
specific case of a valid signature for a *different* payload than the
one submitted.

## What this protects against

- A tampered or forged entry making it into the ledger without a
  genuine biometric check on the device that's supposed to own it.
- Biometric data ever leaving the device.
- A device that was never paired submitting anything at all.

## What this does *not* protect against

- **A LAN eavesdropper**, currently. Client-to-server traffic is
  plain HTTP. On a trusted home/office network behind a normal
  router this is a low-severity gap; it becomes a real one on
  shared/public Wi-Fi. Adding TLS (a self-signed cert the clients
  pin, since there's no public domain to get a real cert for) is the
  natural next step if that threat model applies to you.
- **A compromised device.** If someone's phone is unlocked and
  malware or a malicious app can trigger the biometric prompt itself
  (or the person is coerced into scanning their own finger), the
  signature is still "genuine" from the server's point of view. This
  is true of essentially all biometric-gated signing systems, not
  specific to this design.
- **A lost/stolen paired device that still has a live biometric
  enrolled to someone with access to it.** There's no remote
  revocation yet — see "Known gaps" in ARCHITECTURE.md. Until that
  exists, treat a lost paired device as a live credential.
- **Server-side compromise.** Whoever controls the server machine can
  read and edit the SQLite file directly — signatures protect the
  *submission* path, not data at rest. If that's a concern, disk
  encryption on the server machine is the relevant control, not
  anything in this app.

## Pairing's trust anchor

A new device is only ever authorized using a short code shown on the
server's own screen (see `server/app/auth.py`). The security property
this buys you: someone has to be physically able to read the server's
screen to onboard a new device. That property only holds if you keep
it that way — e.g., don't add a "generate pairing code" button to a
remotely-accessible interface.
