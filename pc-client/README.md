# Voice ledger — PC client

PySide6 desktop app, matching the pattern from MIDA Studio. Typically
runs on the same Windows machine as the server (see
docs/ARCHITECTURE.md) so it can also generate pairing codes for the
phone.

## Get a real .exe (no local Windows machine needed)

1. Push this repo to GitHub.
2. Actions tab → "PC client build (Windows)" runs automatically (or
   trigger it manually via "Run workflow"). It builds on a genuine
   `windows-latest` GitHub runner — this specifically has to happen on
   real Windows, since `winsdk` (the Windows Hello bindings) doesn't
   exist anywhere else.
3. Open the finished run → Artifacts → `voice-ledger-windows-exe` →
   download → `VoiceLedger.exe`.
4. First run will likely trigger a Windows SmartScreen warning ("Windows
   protected your PC") — expected for any app without an expensive
   code-signing certificate, not a sign anything's wrong. "More info" →
   "Run anyway".

## Building it locally instead (on an actual Windows PC)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller pyinstaller-hooks-contrib
pyinstaller voiceledger.spec
```

`dist\VoiceLedger.exe` is the result — same spec file the CI workflow
uses, so both paths produce the same build.

## Status: what's verified vs. not

Verified in the (Linux) sandbox this was built in, headless
(`QT_QPA_PLATFORM=offscreen`): the app imports cleanly, all three
pages (Record / Review / Settings) construct without error, and the
guided-entry-to-payload pipeline (`AppState.build_payload` →
`canonical_json`) was exercised directly and produces correct output.

`biometric_windows.py` byte-compiles correctly but could not be
*executed* anywhere in that process — `winsdk` and Windows Hello only
exist on real Windows. The CI build above will catch import/packaging
issues; the actual Windows Hello prompt and signing round-trip still
need a real run-through on your machine with Windows Hello configured
(a PIN at minimum, a fingerprint reader for the experience this app
is actually going for).

The `KeyCredentialManager` API it's built on is documented by
Microsoft to generate a 2048-bit RSA key and sign with PKCS#1 v1.5/
SHA-256 - the server's `verify_signature()` was updated (and tested)
to accept that alongside the Android client's ECDSA signatures.

## Setup (running from source, for development)

```bash
python3 -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
python main.py
```

## What's still a stub / needs your decisions

- **Persisting settings**: `server_base_url` and `device_id` live in
  `AppState`, in memory only — add a small `QSettings`-backed load/
  save if you want them to survive a restart.
- **History view**: `api_client.list_transactions` is implemented and
  ready to call; no screen shows it yet.
- **First-run Windows Hello activation**: the docs above note a
  historical quirk with `KeyCredentialManager` from unpackaged
  (non-MSIX) desktop apps having the Hello prompt appear behind the
  main window on some Windows versions — if that happens, alt-tab
  finds it; packaging via MSIX is the longer-term fix if it's
  persistent for you.

- **Persisting settings**: `server_base_url` and `device_id` live in
  `AppState`, in memory only — add a small `QSettings`-backed load/
  save if you want them to survive a restart.
- **History view**: `api_client.list_transactions` is implemented and
  ready to call; no screen shows it yet.
- **First-run Windows Hello activation**: the docs above note a
  historical quirk with `KeyCredentialManager` from unpackaged
  (non-MSIX) desktop apps having the Hello prompt appear behind the
  main window on some Windows versions — if that happens, alt-tab
  finds it; packaging via MSIX is the longer-term fix if it's
  persistent for you.
