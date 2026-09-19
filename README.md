# Voice Ledger

[![Android build](https://github.com/AnrixaLabs/voice_ledger/actions/workflows/android-build.yml/badge.svg)](https://github.com/AnrixaLabs/voice_ledger/actions/workflows/android-build.yml)
[![PC build](https://github.com/AnrixaLabs/voice_ledger/actions/workflows/pc-build.yml/badge.svg)](https://github.com/AnrixaLabs/voice_ledger/actions/workflows/pc-build.yml)

Voice-assisted payment and debt-entry system with Android, Windows, and self-hosted server components.

Voice Ledger is designed to capture structured payment records in Armenian, confirm sensitive actions through device authentication, and store the resulting ledger on infrastructure controlled by the user.

## Status

**Functional prototype / active development.** The server and parsing/security flows have automated coverage. Client applications are buildable through the repository workflows, while hardware-dependent behavior still requires device testing.

## Repository layout

```text
android-client/      Kotlin + Jetpack Compose Android client
pc-client/           Python + PySide6 Windows client
server/              FastAPI server and ledger storage
docs/                architecture and security documentation
.github/workflows/   Android and Windows CI/build workflows
```

## Core capabilities

- Armenian voice-entry workflow;
- structured payment/debt records;
- guided capture mode with deterministic parsing;
- device pairing;
- biometric-gated signing on supported clients;
- signature verification and tamper rejection;
- local SQLite ledger storage on the server;
- Android and Windows client builds through GitHub Actions.

## Capture modes

### Guided mode

The client requests fields individually and parses each answer using the local Armenian-language rules. This is the primary offline-capable workflow.

### Free-form mode

The server includes an optional model-assisted extraction path for converting a single transcript into structured fields. This mode requires configured external AI credentials and is intentionally separated from the deterministic guided flow.

## Getting started

Start with the component documentation:

- `server/README.md` — server setup and tests;
- `android-client/README.md` — Android development and build instructions;
- `pc-client/README.md` — Windows client setup and packaging;
- `docs/ARCHITECTURE.md` — system design;
- `docs/SECURITY.md` — security model and limitations.

## CI and builds

Repository workflows build the Android client and Windows client and expose build artifacts from GitHub Actions. Signing material must be supplied through the appropriate secure release configuration and must never be committed.

## Security status

The current design includes device pairing and signed sensitive operations. Transport security and other deployment-hardening items should be reviewed before using the system across untrusted networks.

See `SECURITY.md` and `docs/SECURITY.md` for security guidance.

## License

No open-source license is currently included in this repository.

## Ownership

Maintained by **AnrixaLabs**.
