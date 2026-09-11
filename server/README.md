# Voice ledger — local server

Runs on one PC on your LAN (your office/home machine). Both the
Android and PC clients talk to this over the local network — nothing
here needs to be reachable from the internet.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # faster-whisper is a big install (torch);
                                  # comment it out in requirements.txt first
                                  # if you'd rather start with stt_provider=azure
cp .env.example .env
# edit .env: at minimum set an Azure Speech key/region if you want TTS
# confirmation read-back, or set TTS_PROVIDER=none to skip it.
```

Run it:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8420
```

First launch creates `data/ledger.db` (SQLite) automatically.

## Pairing a new phone or PC client

1. On this machine: `curl -X POST http://localhost:8420/pair/start`
   → returns an 8-character code, valid for 10 minutes.
   (The Android/PC apps will have a "Pair this device" button that
   calls this for you and shows the code on the server console —
   see docs/ARCHITECTURE.md.)
2. On the new device, open the app, choose "Pair", enter the server's
   LAN address (e.g. `192.168.1.42:8420`) and the code.
3. The device generates its signing key pair locally and registers the
   public half. From then on it can submit ledger entries.

## Tests

```bash
python -m pytest tests/ -v
```

`tests/test_nlu.py` exercises the Armenian number/money/date parsers
directly — no server needed. `tests/test_e2e_smoke.py` spins up the
real FastAPI app and walks through pairing, biometric-style signing,
a valid submission, a tampered-payload rejection, and an
unknown-device rejection.

## Capture modes

- **Guided (default, fully offline-capable)**: the app asks for one
  field at a time ("say the name", "say the amount paid", ...). Each
  answer is parsed by `app/nlu/*_hy.py` — no internet, no API cost.
- **Free-form (needs `ANTHROPIC_API_KEY` + internet)**: one long
  utterance, parsed in one shot via `app/nlu/extractor.extract_freeform`.
  Falls back to guided mode if no key is configured.

## What's stubbed vs. real here

Real and tested: pairing, ECDSA signature verification, the
Armenian number/money/date parsers, the SQLite ledger, the
tamper-rejection path.

Needs your own keys before first real use: `AZURE_SPEECH_KEY` (TTS,
and STT if you set `STT_PROVIDER=azure`) and, optionally,
`ANTHROPIC_API_KEY` for free-form mode. `faster-whisper` will download
its model weights on first call if you use `STT_PROVIDER=local`.
