# Architecture

## Components

```
Android client  --\
                    >---  Local server (FastAPI, SQLite)  ---  data/ledger.db
PC client       --/         runs on one machine on your LAN
```

Both clients talk to one server over the local network — no cloud
account, no data leaving your network by default (the optional
free-form mode and Azure TTS/STT are the only things that touch the
internet, and both are off unless you configure keys for them).

## Why this stack

Matches your existing conventions rather than introducing a new one:
FastAPI backend and Kotlin/Compose Android client (same as LocalLens),
PySide6 desktop client (same as MIDA Studio).

## Request flow, end to end

1. **Record**: the app walks through fields one at a time (guided
   mode) — name, place, date, amount paid, amount due, due date —
   recording a short clip for each.
2. **Transcribe**: each clip goes to the server's `/stt` endpoint
   (faster-whisper locally, or Azure Speech).
3. **Parse**: the transcript for that one field goes to
   `/nlu/guided-field`, which runs a small rule-based Armenian parser
   (`server/app/nlu/*_hy.py`) — no LLM call needed for this mode.
4. **Review**: the client shows all six parsed fields back to the
   person before anything is signed.
5. **Confirm**: on "confirm", the client builds a JSON payload from
   those fields and asks the OS for a biometric check — Android's
   `BiometricPrompt` (fingerprint) or Windows Hello. If it succeeds,
   the OS signs the payload with a device-local private key that
   never leaves secure hardware (Android Keystore / Windows TPM). See
   `docs/SECURITY.md` for exactly what this does and doesn't
   guarantee.
6. **Submit**: the payload + signature go to `POST /transactions`.
   The server looks up the device's registered public key (from
   pairing) and verifies the signature. Only on success does the
   entry get written to SQLite.

## Pairing

New devices don't get to submit transactions until they're paired.
The code that authorizes a new device is only ever shown on the
server's own console (or the PC client, when it's running on the
same machine as the server) — see `server/app/auth.py`'s docstring
for the reasoning, and `server/README.md` for the exact steps. The
Android app deliberately has no "generate a code" button of its own,
to keep that physical-presence property meaningful.

## Guided vs. free-form capture

Guided mode (one field at a time) was the default design choice
because Armenian free-form voice parsing — pulling a name, place, two
amounts, and two dates out of one unstructured sentence — is a much
harder NLU problem than parsing one short, single-purpose answer at a
time. Guided mode also means the whole pipeline can run fully
offline: no LLM call, no internet dependency, no per-transaction API
cost. Free-form mode exists in `server/app/nlu/extractor.py` for
when you'd rather just talk naturally, at the cost of needing
`ANTHROPIC_API_KEY` and a network connection; it hasn't been wired
into either client's UI yet.

## Known gaps (see each README for the full list)

- No TLS between clients and server — fine on a trusted LAN, a real
  gap if this ever runs somewhere less trusted.
- No device revocation UI (the `Device.revoked` flag exists in the
  data model; nothing sets it yet).
- Neither client has a transaction-history screen, though both
  `GET /transactions` calls are implemented and ready to use.
