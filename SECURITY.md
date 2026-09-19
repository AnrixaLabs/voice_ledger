# Security Policy

## Reporting

Do not disclose authentication material, device keys, private ledger data, or exploitable security details in a public issue.

Report security-sensitive findings privately to the repository owner through GitHub. Use GitHub private security reporting when available.

## Sensitive material

Never commit:

- signing keys or keystores;
- private device keys;
- API tokens or service credentials;
- real ledger databases or exported financial records;
- passwords or local environment files.

## Deployment boundary

The repository documents a self-hosted architecture. Before exposing a deployment beyond a trusted local network, review transport security, authentication, device revocation, backup protection, and server hardening.

## Supported code

Security fixes should target the current default branch unless a maintained release branch is explicitly documented.
