# Installing Febris client software

Two audiences read this. A node operator pointing a node at this feed, and a person putting the
first application onto a bare tablet by hand.

Five packages are published and every URL in `manifest.json` resolves. The two simulation SDKs at
0.1.0, and the PC suite, Mobile Server and Mobile Companion at 0.2.0.

> **CORRECTED 2026-09-08.** This paragraph used to open **Nothing is published yet**, on the
> grounds that no signing keystore existed and the committed manifest was a worked example with
> `.invalid` URLs. That stopped being true on 2026-09-01. The keystore exists, the clients
> published at v0.2.0, and `manifest.json` on this branch is the live index. The worked example
> with the reserved-TLD URLs is `manifest.sample.json`, a different file.
>
> One caveat survives. The published Android v0.2.0 builds are **debug-signed**. A device that
> takes one cannot be upgraded in place to a release-signed v0.2.1, because Android refuses
> across a signing-certificate change, so it has to uninstall first. Once, at v0.2.1.

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
   sha256sum febris-mobile-server-v0.2.0.zip
   ```

Compare against the `artifact.sha256` for that entry in `manifest.json`. If they differ, stop.
3. Unzip it and sideload the `.apk`. You will need to allow installation from unknown sources,
   which is the standard Android prompt.
4. Point the Mobile Server at your node. From there the node serves everything else.

To check who signed the APK rather than only that it arrived intact:

```bash
unzip -o febris-mobile-server-v0.2.0.zip
apksigner verify --print-certs com.febris.mobileserver.apk
```

Compare the certificate digest against `contains[].signerSha256` in the manifest entry. The
checksum proves the bytes are undamaged. The signer digest is the only field that says anything
about who produced them.

## How the Companion normally reaches a headset

Not by a person downloading it. It reaches a headset by the node serving it to the Mobile Server,
which installs it over ADB on USB OTG. Plan around that route.

> **CORRECTED 2026-09-08.** This section used to say the Companion is listed with
> `consumers: ["node"]` and that the portal refuses to serve it to a browser, returning an
> explanation instead of bytes. Neither holds. The live row carries `["node", "human"]`, the APK
> is a normal asset on the Febris_MobileSuite v0.2.0 release, and no code anywhere implements
> that refusal. The only reader of `consumers` is the node-side feed sync, which uses it to skip
> a row it is not offered.

That is a deliberate path, not a restriction to work around. The Companion expects to be
provisioned by a Server that already knows which node it belongs to.
