# Installing Febris client software

Two audiences read this. A node operator pointing a node at this feed, and a person putting the
first application onto a bare tablet by hand.

**Nothing is published yet.** No signing keystore exists, so no artifact here is real. The
manifest committed to this repository is a worked example whose URLs use the reserved `.invalid`
TLD and whose checksums are counting patterns. The steps below are correct and are not yet
runnable.

---

## If you run a node

Point the node's package-feed sync at the raw manifest URL. The node fetches it, verifies each
artifact against the checksum in the entry, and upserts its own catalogue.

Requirements the node enforces on the URL:

- **It must be `https`.** A plain `http` manifest URL is refused before any fetch happens.
- **It must be absolute.**

Entries are skipped rather than failed when they do not apply to you. An entry is ignored if its
`channel` is not the one you asked for, if it is marked `obsolete`, or if its `consumers` list
does not include `node`.

Two behaviours worth knowing before your first sync:

- **The checksum is verified before ingest, not after.** The artifact is streamed to a temporary
  file and hashed in one pass. A mismatch, a missing checksum or a download over the size ceiling
  is refused with nothing written, so a truncated download never becomes a published package.
- **One bad entry does not abandon the run.** Every package carries its own outcome, and a dry run
  produces the same report while changing nothing. Run one first.

You can host your own manifest instead. It is a static JSON document with no service behind it,
and the schema in this repository is the contract. Nothing about the node requires the feed to be
this repository.

## If you have a bare tablet

The **Mobile Server** is the bootstrap and is meant to be installed by hand. A tablet with no
Febris application on it cannot fetch its own first application, which is why that one artifact is
published for people as well as for nodes.

1. Open the Release and download the Mobile Server `.zip`.
2. Verify it before you install it:

   ```bash
   sha256sum febris-mobile-server-0.2.0.zip
   ```

Compare against the `artifact.sha256` for that entry in `manifest.json`. If they differ, stop.
3. Unzip it and sideload the `.apk`. You will need to allow installation from unknown sources,
   which is the standard Android prompt.
4. Point the Mobile Server at your node. From there the node serves everything else.

To check who signed the APK rather than only that it arrived intact:

```bash
apksigner verify --print-certs febris-mobile-server-0.2.0.apk
```

Compare the certificate digest against `contains[].signerSha256` in the manifest entry. The
checksum proves the bytes are undamaged. The signer digest is the only field that says anything
about who produced them.

## The Companion is not downloadable by a person

`AndroidMobileCompanion` is listed with `consumers: ["node"]` and the portal refuses to serve it
to a browser, returning an explanation instead of bytes. It reaches a headset by the node serving
it to the Mobile Server, which installs it over ADB on USB OTG.

That is a deliberate path, not a restriction to work around. The Companion expects to be
provisioned by a Server that already knows which node it belongs to.
