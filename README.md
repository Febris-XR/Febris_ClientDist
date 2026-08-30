# febris-client-dist

**The distribution feed for Febris client software. A JSON index at the repository root, and the
artifacts themselves attached to GitHub Releases. There is no service here to run.**

A Febris node syncs this feed to learn what client software exists, then downloads and verifies
the artifacts it needs. A person can also read `manifest.json` and follow a link. That is the
whole mechanism.

---

## What is published here today: the two SDKs, nothing else

Read this before you look for a client download.

`manifest.json` currently advertises exactly two packages, and both are real: the **C# Simulation
SDK** (pointing at the published nuget.org package) and the **C++ Simulation SDK** (pointing at
the conformance-gated bundle on the Febris_SDK GitHub Release). Their URLs resolve, their sizes
and sha256 digests are of the live artifacts, and a node syncing this feed catalogs them for
developers. The SDKs are hosted on their canonical channels; this feed only points.

**No CLIENT artifact exists yet.** The Android signing keystore has not been generated, and until
it is, no APK can be published that a device will accept as an upgrade to any later build. The PC
launcher rides the same gate. So the mobile and PC kinds are absent from the live feed, and that
absence is the truthful state rather than an oversight.

`manifest.sample.json` sits beside it as the worked example covering every kind. Its two Android
rows are deliberately non-functional (URLs on the `.invalid` TLD that RFC 2606 reserves so they
can never resolve, checksums that are counting patterns); its two SDK rows mirror the live feed.

**Do not copy the Android rows' URLs or checksums into anything.**

## Why a file and not an API

GitHub Releases plus a JSON index gives versioning, CDN delivery, immutable artifacts, checksums,
release notes and an audit trail, with nothing to operate and no uptime obligation. Distribution
here is read-mostly over artifacts that never change once published, so a running service would
add a deployment without buying anything the static feed does not already provide.

Artifacts attach to Releases and are **never committed to git**. They are tens of megabytes and
git would keep every version forever.

## What is in here

| Path | What it is |
|---|---|
| `manifest.json` | the live index, always current on the default branch. Empty today |
| `manifest.sample.json` | a worked example, deliberately non-functional |
| `schema/manifest.schema.json` | the feed contract, JSON Schema 2020-12, versioned |
| `tools/validate_manifest.py` | the pull-request gate, standard library only |
| `docs/INSTALL.md` | how a node operator or a bare device consumes this |

## The manifest in one screen

```json
{
  "schemaVersion": 1,
  "generated": "2026-07-29T00:00:00Z",
  "packages": [
    {
      "uuid": "11111111-1111-4111-8111-111111111111",
      "kind": "AndroidMobileServer",
      "kindId": 200,
      "version": "0.2.0",
      "versionCode": 200,
      "channel": "stable",
      "consumers": ["human", "node"],
      "packageName": "com.febris.mobileserver",
      "obsolete": false,
      "artifact": { "fileName": "...zip", "url": "...", "sizeBytes": 0, "sha256": "..." },
      "contains": [ { "fileName": "...apk", "sha256": "...", "signerSha256": "..." } ]
    }
  ]
}
```

`schemaVersion` moves only on a breaking change to the document shape, and a consumer must refuse
a value it does not recognise rather than guess. `generated` is informational and must never be
used to decide which package is newest, because regenerating a manifest is not a release.

## Two fields that are easy to get wrong

**`consumers` is not decoration.** The two mobile artifacts do not travel the same way:

- `AndroidMobileServer` is `["human", "node"]`. It is the **bootstrap**, so a person must be able
  to click a link and sideload it. A tablet with no Febris app on it cannot fetch its own first
  app.
- `AndroidMobileCompanion` is `["node"]`. The portal deliberately refuses to serve it to a browser
  and returns an explanatory page instead of bytes. It reaches the headset by the node serving it
  to the mobile Server, which installs it over ADB on USB OTG.

A consumer that ignores the field still works, so this is documentation with teeth rather than a
gate.

**`signerSha256` is the only field that proves origin.** `artifact.sha256` proves the bytes
arrived intact, which is worth nothing against a hostile publisher, because whoever serves the
file also serves the checksum. `signerSha256` is the digest of the APK **signing certificate**, so
a node that pins it can refuse an artifact signed by anyone else. Read it off a built APK with:

```bash
apksigner verify --print-certs febris-mobile-server-0.2.0.apk
```

Nodes do not enforce it yet. Publishing it now means the pin is available the day they do.

## Licence, and the offer of source

**AGPL-3.0-only.** See [LICENSE](LICENSE).

Distributing binaries under this licence obliges the distributor to offer the **corresponding
source** for those exact binaries. Every Release published here carries a written offer naming the
repository and the exact commit its artifacts were built from. That offer is part of the release,
not a courtesy, and the release workflow refuses to publish without it.

The client applications are AGPL because the platform is. On a device rather than a server the
network-use clause has little practical reach, so in effect it behaves as GPL-3.0 does.

## Security

Report vulnerabilities privately through this repository's Security tab. See
[SECURITY.md](SECURITY.md). Please do not open a public issue for a security bug.

A manifest entry pointing at bytes that are not what they claim to be is a security issue, not a
packaging one.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Most changes here are manifest changes, and the validator
runs on every pull request.
