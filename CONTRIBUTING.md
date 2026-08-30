# Contributing

Most changes here are changes to `manifest.json`. The validator runs on every pull request and it
is the gate, so run it before you push.

## The validator

```bash
python tools/validate_manifest.py manifest.json
```

Standard library only, deliberately. A validator that needs `pip install` before it can tell you
the manifest is broken is a validator that gets skipped. It exits 0 when every file passes and 1
otherwise, and its output is ASCII.

It enforces the schema plus three cross-field rules that JSON Schema expresses poorly, each of
which is a mistake that has a real failure mode rather than a hypothetical one:

- **`kind` and `kindId` must agree.** They are redundant so that no consumer keeps a name-to-enum
  mapping in sync. A disagreement is therefore a manifest bug, not something a consumer should
  resolve in favour of one side.
- **`uuid` must be unique.** A node upserts its catalogue row keyed on it, so two entries sharing
  one silently collapse into a single row.
- **`(kind, channel, versionCode)` must be unique.** Android cannot install two builds sharing a
  `versionCode` as upgrades, and that surfaces on a device as "the APK did not install" rather
  than as a manifest problem.

It is confirmed to REJECT rather than merely to pass the good case: a kind and kindId mismatch, a
duplicate uuid, a duplicate `(kind, channel, versionCode)`, a malformed Android application id, a
missing `versionCode` on an Android kind, an uppercase digest, a plain-`http` artifact URL, an
unknown field, a `minSdk` above `targetSdk`, and an unknown `schemaVersion`.

## A published entry is immutable

This is the rule that matters most, because breaking it is silent.

Once an entry has been published, **the bytes behind its `uuid` never change**. A node that has
already ingested it will not re-download, and one that has not will get different bytes from the
same identity than its neighbour did. If a release was wrong, add a new entry with a new `uuid`
and a higher `versionCode`, and set `obsolete: true` on the old one. Do not edit it in place and
do not reuse a `uuid`.

The same applies to `packageName`. An Android application id is permanent once published, on the
same footing as the signing key: changing it means every user uninstalls and loses local data.

## Checksums are computed, never typed

Every `sha256` must be the real digest of the artifact you are publishing.

```bash
sha256sum febris-mobile-server-0.2.0.zip
apksigner verify --print-certs febris-mobile-server-0.2.0.apk   # for signerSha256
```

The release workflow recomputes them and refuses to publish if the manifest disagrees, so a typed
checksum fails the build rather than shipping.

## Artifacts are built locally, and that is deliberate

CI does not compile the mobile applications. The Android heads are classic Xamarin, which is out
of support and is not available on GitHub-hosted runner images, so compilation stays on a
developer machine. CI handles what it can do reliably: validating, checksumming, regenerating the
manifest and cutting the Release.

That split is a constraint rather than a preference. It also means the person cutting a release is
attesting that the artifact they attached is the one they built.

## Releasing

1. Build and sign the artifacts locally.
2. Open a pull request updating `manifest.json`. `validate.yml` checks the schema and the
   cross-field rules, and confirms every artifact URL resolves.
3. Merge, then tag `vX.Y.Z`. `release.yml` validates, recomputes checksums against the attached
   artifacts, and cuts the Release.

The release notes carry the written offer of corresponding source, naming the exact commit the
artifacts were built from. That offer is a licence obligation, not a formality, and the workflow
will not publish a release without it.

## Reporting a security issue

Do not open a public issue. See [SECURITY.md](SECURITY.md) for the private reporting channel. A
manifest entry pointing at bytes that are not what they claim to be is a security issue.

## Licence

By contributing you agree that your contributions are licensed under AGPL-3.0-only, the same
licence as the project. See [LICENSE](LICENSE).
