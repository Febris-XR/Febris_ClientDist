# febris-client-dist

**The distribution feed for Febris client software. A JSON index at the repository root, and the
artifacts themselves attached to GitHub Releases. There is no service here to run.**

A Febris node syncs this feed to learn what client software exists, then downloads and verifies
the artifacts it needs. A person can also read `manifest.json` and follow a link. That is the
whole mechanism.

---

## What is published here today

Read this before you look for a client download.

`manifest.json` advertises **five** packages, and every one of them is real.

| Kind | Version | Where the bytes live |
|---|---|---|
| `CSharp` | 0.1.0 | the published nuget.org package |
| `CPP` | 0.1.0 | the conformance-gated bundle on the Febris_SDK release |
| `PC` | 0.2.0 | the Febris_PC v0.2.0 release |
| `AndroidMobileServer` | 0.2.0 | the Febris_MobileSuite v0.2.0 release |
| `AndroidMobileCompanion` | 0.2.0 | the Febris_MobileSuite v0.2.0 release |

Their URLs resolve, their sizes and sha256 digests are of the live artifacts, and a node syncing
this feed catalogues them. Nothing is hosted here. Every artifact sits on its own project's
release page and this feed only points at it.

> **CORRECTED 2026-09-08.** This section used to be headed "the two SDKs, nothing else" and said
> **No CLIENT artifact exists yet**, on the grounds that the Android signing keystore had not been
> generated. Both statements were overtaken on 2026-09-01, when the PC suite and the Android suite
> published at v0.2.0 and their rows entered this feed. The keystore exists.
>
> One thing the old text got right is worth keeping. The published Android v0.2.0 builds are
> **debug-signed**, so a device that installs one cannot take a release-signed v0.2.1 as an
> upgrade. Android refuses across a signing-certificate change and the device has to uninstall
> first. That happens once, at v0.2.1, and never again.

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
| `manifest.json` | the live index, always current on the default branch. Five packages today |
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
- `AndroidMobileCompanion` is `["node", "human"]`. It normally reaches a headset by the node
  serving it to the mobile Server, which installs it over ADB on USB OTG, and that is the route
  to plan around.

  > **CORRECTED 2026-09-08.** This entry used to read `["node"]` and to say the portal refuses to
  > serve the Companion to a browser, returning an explanatory page instead of bytes. Neither is
  > true. The live row carries `["node", "human"]`, and no code anywhere implements that refusal.
  > The only reader of `consumers` is the node-side feed sync, which uses it to skip a row it is
  > not offered. The portal does the opposite and maps the Companion to a public download anchor.

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
