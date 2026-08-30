#!/usr/bin/env python3
"""Validate a client-distribution manifest.

Pure standard library on purpose: this runs as the public distribution repo's pull-request gate,
and a validator that needs `pip install` before it can tell you the manifest is broken is a
validator that gets skipped.

It enforces the invariants from schema/manifest.schema.json plus three cross-field rules a JSON
Schema expresses poorly:

  * kind and kindId must agree. They are redundant on purpose, so that no consumer has to keep a
    name-to-enum mapping in sync, which means a disagreement is a fatal manifest error rather than
    something to resolve in favour of one side.
  * uuid must be unique across packages. The node upserts its catalog row keyed on uuid, so two
    packages sharing one would silently collapse into a single row.
  * (kind, channel, versionCode) must be unique. Two builds of the same kind claiming the same
    Android versionCode cannot both be installed as upgrades, and the failure surfaces on a device
    as "the APK did not install" rather than as a manifest problem.

Usage:
    python validate_manifest.py <manifest.json> [...]

Exits 0 when every file passes, 1 otherwise. Output is ASCII only.
"""

import json
import re
import sys

SCHEMA_VERSION = 1

KINDS = {
    "PC": 100,
    "AndroidMobileServer": 200,
    "AndroidMobileCompanion": 300,
    "CSharp": 400,
    "CPP": 500,
}
ANDROID_KIND_IDS = {200, 300}

CHANNELS = {"stable", "beta"}
CONSUMERS = {"human", "node"}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
PACKAGE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
ZIP_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.zip$")
# The CSharp SDK kind (400) alone may point at the published .nupkg -- that IS
# its canonical artifact (zip-format internally); rewrapping it would create a
# second artifact nobody publishes. Every other kind keeps the .zip envelope
# the deployed mobile client depends on.
NUPKG_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.nupkg$")
NUPKG_ALLOWED_KIND_IDS = {400}

ROOT_REQUIRED = ("schemaVersion", "generated", "packages")
ROOT_ALLOWED = set(ROOT_REQUIRED)

PKG_REQUIRED = (
    "uuid", "kind", "kindId", "name", "version", "channel", "consumers", "obsolete", "artifact",
)
PKG_ALLOWED = set(PKG_REQUIRED) | {
    "versionCode", "description", "language", "packageName",
    "minSdk", "targetSdk", "contains", "releaseNotes",
}

ARTIFACT_REQUIRED = ("fileName", "url", "sizeBytes", "sha256")
ARTIFACT_ALLOWED = set(ARTIFACT_REQUIRED)

CONTAINS_REQUIRED = ("fileName", "sha256")
CONTAINS_ALLOWED = set(CONTAINS_REQUIRED) | {"signerSha256"}


def check_keys(errors, where, obj, required, allowed):
    if not isinstance(obj, dict):
        errors.append("%s: expected an object, got %s" % (where, type(obj).__name__))
        return False
    for key in required:
        if key not in obj:
            errors.append("%s: missing required field '%s'" % (where, key))
    for key in obj:
        if key not in allowed:
            errors.append("%s: unknown field '%s'" % (where, key))
    return True


def check_positive_int(errors, where, value):
    # bool is a subclass of int in Python, and `true` is not a byte count.
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        errors.append("%s: expected a positive integer, got %r" % (where, value))


def validate_artifact(errors, where, artifact, kind_id=None):
    if not check_keys(errors, where, artifact, ARTIFACT_REQUIRED, ARTIFACT_ALLOWED):
        return
    name = artifact.get("fileName")
    if isinstance(name, str) and not ZIP_NAME_RE.match(name):
        if kind_id in NUPKG_ALLOWED_KIND_IDS and NUPKG_NAME_RE.match(name):
            pass  # kind 400's canonical artifact is the published .nupkg
        else:
            errors.append(
                "%s.fileName: must be a plain .zip name with no path separators "
                "(.nupkg is legal only for the CSharp kind, 400), got %r" % (where, name)
            )
    url = artifact.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        errors.append("%s.url: expected an http(s) URL, got %r" % (where, url))
    elif url.startswith("http://"):
        errors.append(
            "%s.url: plain http, so the artifact and its checksum can both be rewritten in transit. "
            "Use https" % where
        )
    check_positive_int(errors, where + ".sizeBytes", artifact.get("sizeBytes"))
    digest = artifact.get("sha256")
    if not isinstance(digest, str) or not SHA256_RE.match(digest):
        errors.append("%s.sha256: expected 64 lowercase hex characters, got %r" % (where, digest))


def validate_contains(errors, where, entries):
    if not isinstance(entries, list):
        errors.append("%s: expected an array" % where)
        return
    for index, entry in enumerate(entries):
        entry_where = "%s[%d]" % (where, index)
        if not check_keys(errors, entry_where, entry, CONTAINS_REQUIRED, CONTAINS_ALLOWED):
            continue
        if not isinstance(entry.get("fileName"), str) or not entry["fileName"]:
            errors.append("%s.fileName: expected a non-empty string" % entry_where)
        for field in ("sha256", "signerSha256"):
            if field in entry:
                value = entry[field]
                if not isinstance(value, str) or not SHA256_RE.match(value):
                    errors.append(
                        "%s.%s: expected 64 lowercase hex characters, got %r"
                        % (entry_where, field, value)
                    )


def validate_package(errors, index, pkg):
    where = "packages[%d]" % index
    if not check_keys(errors, where, pkg, PKG_REQUIRED, PKG_ALLOWED):
        return

    uuid = pkg.get("uuid")
    if not isinstance(uuid, str) or not UUID_RE.match(uuid):
        errors.append("%s.uuid: expected a UUID, got %r" % (where, uuid))

    kind = pkg.get("kind")
    kind_id = pkg.get("kindId")
    if kind not in KINDS:
        errors.append("%s.kind: unknown kind %r, expected one of %s"
                      % (where, kind, ", ".join(sorted(KINDS))))
    if kind_id not in set(KINDS.values()):
        errors.append("%s.kindId: unknown kindId %r" % (where, kind_id))
    if kind in KINDS and KINDS[kind] != kind_id:
        errors.append(
            "%s: kind %r and kindId %r disagree. kind %r is %d. They are redundant on purpose, so a "
            "mismatch is a manifest bug and not something a consumer should resolve"
            % (where, kind, kind_id, kind, KINDS[kind])
        )

    if not isinstance(pkg.get("name"), str) or not pkg["name"]:
        errors.append("%s.name: expected a non-empty string" % where)
    if not isinstance(pkg.get("version"), str) or not pkg["version"]:
        errors.append("%s.version: expected a non-empty string" % where)
    if pkg.get("channel") not in CHANNELS:
        errors.append("%s.channel: expected one of %s, got %r"
                      % (where, ", ".join(sorted(CHANNELS)), pkg.get("channel")))
    if not isinstance(pkg.get("obsolete"), bool):
        errors.append("%s.obsolete: expected a boolean, got %r" % (where, pkg.get("obsolete")))

    consumers = pkg.get("consumers")
    if not isinstance(consumers, list) or not consumers:
        errors.append("%s.consumers: expected a non-empty array" % where)
    else:
        if len(set(consumers)) != len(consumers):
            errors.append("%s.consumers: contains duplicates" % where)
        for value in consumers:
            if value not in CONSUMERS:
                errors.append("%s.consumers: unknown consumer %r, expected human and/or node"
                              % (where, value))

    if kind_id in ANDROID_KIND_IDS:
        for field in ("versionCode", "packageName", "minSdk", "targetSdk"):
            if field not in pkg:
                errors.append(
                    "%s: kind %s requires '%s'" % (where, kind, field)
                )
        check_positive_int(errors, where + ".versionCode", pkg.get("versionCode"))
        check_positive_int(errors, where + ".minSdk", pkg.get("minSdk"))
        check_positive_int(errors, where + ".targetSdk", pkg.get("targetSdk"))
        pkg_name = pkg.get("packageName")
        if isinstance(pkg_name, str) and not PACKAGE_NAME_RE.match(pkg_name):
            errors.append(
                "%s.packageName: %r is not a valid Android application id. This value is PERMANENT "
                "once published" % (where, pkg_name)
            )
        if isinstance(pkg.get("minSdk"), int) and isinstance(pkg.get("targetSdk"), int):
            if pkg["minSdk"] > pkg["targetSdk"]:
                errors.append("%s: minSdk %d is above targetSdk %d"
                              % (where, pkg["minSdk"], pkg["targetSdk"]))

    if "artifact" in pkg:
        validate_artifact(errors, where + ".artifact", pkg["artifact"], pkg.get("kindId"))
    if "contains" in pkg:
        validate_contains(errors, where + ".contains", pkg["contains"])


def validate(manifest):
    errors = []
    if not check_keys(errors, "<root>", manifest, ROOT_REQUIRED, ROOT_ALLOWED):
        return errors

    if manifest.get("schemaVersion") != SCHEMA_VERSION:
        errors.append(
            "<root>.schemaVersion: this validator understands %d, manifest declares %r. Refusing "
            "rather than guessing" % (SCHEMA_VERSION, manifest.get("schemaVersion"))
        )
    if not isinstance(manifest.get("generated"), str):
        errors.append("<root>.generated: expected an ISO-8601 timestamp string")

    packages = manifest.get("packages")
    if not isinstance(packages, list):
        errors.append("<root>.packages: expected an array")
        return errors

    for index, pkg in enumerate(packages):
        validate_package(errors, index, pkg)

    seen_uuids = {}
    seen_versions = {}
    for index, pkg in enumerate(packages):
        if not isinstance(pkg, dict):
            continue
        uuid = pkg.get("uuid")
        if isinstance(uuid, str):
            if uuid in seen_uuids:
                errors.append(
                    "packages[%d].uuid: %s already used by packages[%d]. The node upserts its "
                    "catalog row keyed on uuid, so duplicates collapse into one row"
                    % (index, uuid, seen_uuids[uuid])
                )
            else:
                seen_uuids[uuid] = index
        key = (pkg.get("kind"), pkg.get("channel"), pkg.get("versionCode"))
        if key[2] is not None:
            if key in seen_versions:
                errors.append(
                    "packages[%d]: kind %s on channel %s already claims versionCode %s at "
                    "packages[%d]. Android cannot install two builds with the same versionCode as "
                    "upgrades" % (index, key[0], key[1], key[2], seen_versions[key])
                )
            else:
                seen_versions[key] = index

    return errors


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: validate_manifest.py <manifest.json> [...]\n")
        return 2

    failed = False
    for path in argv[1:]:
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                manifest = json.load(handle)
        except (OSError, ValueError) as exc:
            print("FAIL %s: could not read as JSON: %s" % (path, exc))
            failed = True
            continue

        errors = validate(manifest)
        if errors:
            failed = True
            print("FAIL %s: %d problem(s)" % (path, len(errors)))
            for error in errors:
                print("  - %s" % error)
        else:
            count = len(manifest.get("packages", []))
            print("OK   %s: %d package(s)" % (path, count))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
