# Contributing

Voice Ledger is maintained by AnrixaLabs.

## Before contributing

For non-trivial changes, open an issue describing the problem, intended behavior, and affected component before preparing a pull request.

The repository contains Android, Windows, and server components. Keep changes scoped to the relevant component unless a cross-component change is required.

## Pull requests

A pull request should:

- explain the behavioral change;
- include tests when practical;
- identify any hardware-dependent verification still required;
- avoid weakening pairing, signing, authentication, or tamper checks;
- avoid committing generated binaries, real ledger data, credentials, keys, or local environment files.

## Security issues

Do not report exploitable security issues, credentials, device keys, or private ledger data in public issues. Follow `SECURITY.md`.
