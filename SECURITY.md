# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**. Do not open a public issue for a
security bug.

Use this repository's **[Report a vulnerability](https://github.com/Febris-XR/Febris_ClientDist/security/advisories/new)**
tab (Security -> Advisories -> Report a vulnerability). That channel is private between you
and the maintainers until a fix is published.

Please include the affected component, a description, and reproduction steps or a proof of
concept.

We will acknowledge receipt, investigate, and coordinate a fix and a disclosure timeline
with you.

## Supported versions

This project is pre-1.0. Security fixes land on the default branch. There is no long-term
support branch yet.

## Secret scanning

Every release export is scanned before publication with **both** gitleaks (full history,
`--log-opts=--all`) and **trufflehog** (filesystem and git, verified mode). The gate is
*zero un-allowlisted findings*.

The allowlist is committed in this repository at [`.gitleaks.toml`](.gitleaks.toml) so the
exclusions are auditable rather than asserted. Entries are classified false positives:
vendored third-party assets, deliberate dummy fixtures, runtime-generated test keys, and
reserved `example.*` placeholder domains. If you believe an allowlist entry is hiding a real
credential, that is itself worth reporting through the channel above.
