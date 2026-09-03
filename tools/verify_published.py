#!/usr/bin/env python3
"""Verify that the feed describes the bytes it actually points at.

Usage:
    python verify_published.py <manifest.json>

Exits 0 when every non-obsolete row checks out, 1 otherwise. Output is ASCII only.

WHAT THIS PROVES, AND WHY IT IS NOT THE SAME AS validate_manifest.py.

validate_manifest.py is a SCHEMA check. It reads the JSON and confirms the shape is legal without
touching the network, which is why it can run on every pull request. It cannot tell you whether
`sha256` is the digest of anything real.

This script does the other half. It downloads each artifact from its own `url` and re-derives the
digest and size from the bytes a consumer would actually receive. A mistyped checksum, a re-uploaded
asset, a truncated artifact or a URL pointing at the wrong release all fail here rather than reaching
a node.

It also opens each archive and verifies the `contains` entries inside it. Those are not decoration.
The landing page renders `contains[0]` beside the download button, so a wrong digest there is a
checksum a visitor is invited to run and watch fail on a perfectly good download.

This costs a full download of every artifact, roughly 150 MB today, so it belongs on the release
path rather than on every pull request.
"""

import hashlib
import io
import json
import sys
import urllib.request
import zipfile

TIMEOUT = 180
UA = "febris-clientdist-verify"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def check_bytes(problems, label, blob, declared_sha, declared_size):
    """Compare real bytes against what the manifest claims about them."""
    actual = hashlib.sha256(blob).hexdigest()
    want = (declared_sha or "").lower()
    if actual != want:
        problems.append("%s sha256 is %s but the manifest declares %s"
                        % (label, actual, want or "nothing"))
    if declared_size is not None and len(blob) != declared_size:
        problems.append("%s is %d bytes but the manifest declares %s"
                        % (label, len(blob), declared_size))


def verify_contains(problems, uuid, name, blob, entries):
    """The archive must really hold the files the row says it holds."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
    except Exception as exc:
        problems.append("%s: %s declares contains[] but is not a readable archive (%s)"
                        % (uuid, name, exc))
        return
    held = set(archive.namelist())
    for entry in entries:
        inner = entry.get("fileName")
        if inner not in held:
            problems.append("%s: contains[] names %r but it is not inside %s"
                            % (uuid, inner, name))
            continue
        check_bytes(problems, "%s: %s inside %s" % (uuid, inner, name),
                    archive.read(inner), entry.get("sha256"), entry.get("sizeBytes"))


def verify(manifest):
    problems = []
    checked = 0

    for pkg in manifest.get("packages", []):
        uuid = pkg.get("uuid", "?")
        if pkg.get("obsolete"):
            # An obsolete row describes a release that already happened. It is kept so a node can
            # recognise what it already holds, and its bytes are not this release's concern.
            continue

        artifact = pkg.get("artifact") or {}
        name, url = artifact.get("fileName"), artifact.get("url")
        if not name or not url:
            problems.append("%s: row has no artifact.fileName or artifact.url" % uuid)
            continue

        try:
            blob = fetch(url)
        except Exception as exc:
            problems.append("%s: %s could not be fetched from %s (%s)" % (uuid, name, url, exc))
            continue

        check_bytes(problems, "%s: %s" % (uuid, name), blob,
                    artifact.get("sha256"), artifact.get("sizeBytes"))
        checked += 1
        print("   fetched %-44s %10d bytes" % (name, len(blob)))

        entries = pkg.get("contains") or []
        if entries:
            verify_contains(problems, uuid, name, blob, entries)

    if not checked:
        problems.append("no non-obsolete row was verified, so this release would publish nothing "
                        "the manifest describes")
    return problems, checked


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip())
        return 2
    manifest = json.load(io.open(argv[1], encoding="utf-8-sig"))
    problems, checked = verify(manifest)

    if problems:
        print("\nVERIFICATION FAILED. Nothing has been published.\n")
        for problem in problems:
            print("  - %s" % problem)
        return 1

    print("\nOK   verified %d artifact(s) against the bytes their URLs actually serve" % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
