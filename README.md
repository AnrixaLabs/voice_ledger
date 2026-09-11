# Voice ledger

Speak a payment entry in Armenian — who, where, how much was paid,
how much is still owed, and by when — confirm it with a fingerprint
(phone) or Windows Hello (PC), and it lands in a ledger on a server
that runs on your own machine.

```
android-client/     Kotlin + Jetpack Compose phone app
pc-client/           Python + PySide6 desktop app
server/              Python + FastAPI local server (the ledger lives here)
docs/                Architecture and security notes
.github/workflows/   CI that builds a real .apk and a real .exe
```

## Get the actual app files

Neither binary can be built in a plain sandbox (no Android SDK/Google
Maven access, no Windows machine) — that's not a permissions thing,
it's a missing-toolchain thing. Fastest real path:

1. Push this repo to GitHub.
2. Actions tab → both workflows run automatically on push, or trigger
   them by hand with "Run workflow":
   - **Android build** → Artifacts → `voice-ledger-debug-apk`
   - **PC client build (Windows)** → Artifacts → `voice-ledger-windows-exe`
3. Download, install, done. Full detail (including how to get a
   *signed* release APK instead of a debug one) is in each client's
   README.

If you'd rather build locally: Android Studio for the APK, or
`pyinstaller voiceledger.spec` on an actual Windows machine for the
.exe — also covered in those READMEs.

## Start here

- **`server/README.md`** — get the server running; this is the only
  piece with a full, passing test suite (30 tests: the Armenian
  number/money/date parsers, plus an end-to-end pairing + biometric-
  style signing + tamper-rejection flow against the real app).
- **`docs/ARCHITECTURE.md`** — how the three pieces fit together and
  why they're built the way they are.
- **`docs/SECURITY.md`** — what the biometric signature actually
  protects, and what it doesn't.
- **`android-client/README.md`** / **`pc-client/README.md`** — setup
  for each client, how to get a real build, and an honest list of
  what's verified vs. what needs a real-hardware test pass.

## The two capture modes

- **Guided (default)**: the app asks for one field at a time — "say
  the name", "say how much was paid" — and parses each answer with a
  small rule-based Armenian parser. Fully offline-capable, no API
  cost, and this is the path with real test coverage.
- **Free-form**: say everything in one breath; the transcript is sent
  to Claude to extract all fields at once. Needs an internet
  connection and an Anthropic API key. Falls back to guided mode if
  neither is available. Only the server-side extraction is built;
  neither client has a free-form UI yet (see their READMEs).

## What's genuinely done vs. what's next

**Solid and tested:** the security model (device pairing, biometric-
gated signing, signature verification for both Android's EC keys and
Windows Hello's RSA keys, tamper rejection), the Armenian NLU
parsers, the SQLite ledger.

**Written but needs a real-hardware pass:** both client UIs — see
each client's README for exactly what CI does and doesn't catch, and
what to check by hand once you have the built app in front of you.

**Not started:** TLS between clients and the server (currently plain
HTTP — fine on a trusted home/office LAN, worth revisiting if this
ever runs on shared/public WiFi; see docs/SECURITY.md), device
revocation UI, mDNS auto-discovery of the server, transaction history
screens on either client, and a launcher icon for the Android app.
