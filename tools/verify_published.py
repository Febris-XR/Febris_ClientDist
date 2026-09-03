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
import struct
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


# ---------------------------------------------------------------------------------------------
# READING THE VERSION OUT OF AN APK, AND WHY THE DIGEST CHECK IS NOT ENOUGH.
#
# Everything above proves the bytes are the bytes the manifest names. It cannot prove those bytes
# were BUILT at the version the row advertises. Those are different claims. An APK whose manifest
# says 0.2.0 installs perfectly well while the feed calls it 0.2.1, every digest matches, and the
# mismatch only surfaces on a device after publishing. Android identifiers are permanent once an
# APK ships, so that is the worst possible moment to find out.
#
# The APK carries no version in its filename either. The archive is named for the release but the
# APK inside it is just com.febris.mobileserver.apk, so there is nothing to compare against
# without opening it.
#
# AndroidManifest.xml inside an APK is binary AXML rather than text, so it has to be decoded.
# This is a deliberately small reader. It walks the chunk list for the <manifest> element and
# pulls two attributes off it. It does not attempt to be a general AXML parser, because the only
# question being asked is what version this file claims to be. aapt would answer it too, but that
# would mean requiring the Android SDK on a machine whose whole job is fetching and hashing.

AXML_TYPE = 0x0003
AXML_STRING_POOL = 0x0001
AXML_START_ELEMENT = 0x0102
AXML_UTF8_FLAG = 1 << 8


class AxmlError(Exception):
    """The APK could not be read. Never swallowed, because silence here is the original defect."""


def _axml_len(blob, pos):
    """UTF-8 string pool lengths are one byte, or two when the high bit is set."""
    n = blob[pos]
    if n & 0x80:
        return ((n & 0x7F) << 8) | blob[pos + 1], pos + 2
    return n, pos + 1


def _axml_string_pool(blob, start):
    chunk_type, header_size, _size, count, _styles, flags, strings_start, _ss = \
        struct.unpack_from("<HHIIIIII", blob, start)
    if chunk_type != AXML_STRING_POOL:
        raise AxmlError("expected a string pool at offset %d, found chunk type 0x%04x"
                        % (start, chunk_type))
    offsets = struct.unpack_from("<%dI" % count, blob, start + header_size)
    base = start + strings_start
    utf8 = bool(flags & AXML_UTF8_FLAG)
    out = []
    for off in offsets:
        pos = base + off
        if utf8:
            _chars, pos = _axml_len(blob, pos)
            nbytes, pos = _axml_len(blob, pos)
            out.append(blob[pos:pos + nbytes].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", blob, pos)[0]
            pos += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", blob, pos)[0]
                pos += 2
            out.append(blob[pos:pos + n * 2].decode("utf-16-le", "replace"))
    return out


def _axml_manifest_attributes(blob, pos, strings):
    """Pull versionName and versionCode off a <manifest> start-element chunk.

    Layout is ResXMLTree_node (16 bytes) then ResXMLTree_attrExt, whose attributeStart is an
    offset from the start of attrExt rather than from the chunk, which is the easy thing to get
    wrong here.
    """
    attr_start, attr_size, attr_count = struct.unpack_from("<HHH", blob, pos + 24)
    base = pos + 16 + attr_start
    found = {}
    for i in range(attr_count):
        at = base + i * attr_size
        name_ref = struct.unpack_from("<I", blob, at + 4)[0]
        raw_ref = struct.unpack_from("<i", blob, at + 8)[0]
        data = struct.unpack_from("<I", blob, at + 16)[0]
        key = strings[name_ref] if name_ref < len(strings) else ""
        if key == "versionName":
            found["versionName"] = (strings[raw_ref] if 0 <= raw_ref < len(strings)
                                    else str(data))
        elif key == "versionCode":
            found["versionCode"] = data
    return found


def apk_version(apk_bytes):
    """Return {versionName, versionCode} as the APK itself declares them."""
    try:
        axml = zipfile.ZipFile(io.BytesIO(apk_bytes)).read("AndroidManifest.xml")
    except Exception as exc:
        raise AxmlError("no readable AndroidManifest.xml inside the APK (%s)" % exc)

    if len(axml) < 8 or struct.unpack_from("<H", axml, 0)[0] != AXML_TYPE:
        raise AxmlError("AndroidManifest.xml is not binary AXML")

    header_size = struct.unpack_from("<H", axml, 2)[0]
    strings = _axml_string_pool(axml, header_size)

    pos = header_size
    while pos + 8 <= len(axml):
        chunk_type, _hsize, chunk_size = struct.unpack_from("<HHI", axml, pos)
        if chunk_size < 8:
            break
        if chunk_type == AXML_START_ELEMENT:
            name_ref = struct.unpack_from("<I", axml, pos + 20)[0]
            if name_ref < len(strings) and strings[name_ref] == "manifest":
                return _axml_manifest_attributes(axml, pos, strings)
        pos += chunk_size
    raise AxmlError("no <manifest> element found in AndroidManifest.xml")


def verify_declared_version(problems, uuid, pkg, name, blob, entries):
    """The APK must have been BUILT at the version the row advertises.

    Only Android rows carry a versionCode, and only they are checked here. For every other kind
    the internal version is left unread and said so out loud, because a check that quietly covers
    three of five rows reads as if it covered all five.
    """
    declared_code = pkg.get("versionCode")
    if declared_code is None:
        print("      version inside the artifact not read, this kind carries no versionCode")
        return

    apks = [e.get("fileName") for e in entries
            if (e.get("fileName") or "").lower().endswith(".apk")]
    if len(apks) != 1:
        problems.append("%s: declares versionCode %s but contains[] names %d apk(s), so there is "
                        "nothing unambiguous to check it against" % (uuid, declared_code, len(apks)))
        return

    try:
        archive = zipfile.ZipFile(io.BytesIO(blob))
        actual = apk_version(archive.read(apks[0]))
    except Exception as exc:
        problems.append("%s: could not read the version out of %s (%s)" % (uuid, apks[0], exc))
        return

    declared_name = pkg.get("version")
    got_name = actual.get("versionName")
    got_code = actual.get("versionCode")

    if got_name != declared_name:
        problems.append("%s: %s was built as versionName %r but the row advertises %r"
                        % (uuid, apks[0], got_name, declared_name))
    if got_code != declared_code:
        problems.append("%s: %s was built as versionCode %r but the row declares %r"
                        % (uuid, apks[0], got_code, declared_code))
    if got_name == declared_name and got_code == declared_code:
        print("      built as versionName %s, versionCode %s, matching the row"
              % (got_name, got_code))


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
        verify_declared_version(problems, uuid, pkg, name, blob, entries)

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
