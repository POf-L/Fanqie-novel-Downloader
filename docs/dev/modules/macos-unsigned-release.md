# Unsigned macOS Release Channel

## Responsibility

`.github/workflows/publish-unsigned-macos.yml` publishes a dedicated macOS
client when Apple Developer ID signing and notarization are unavailable. It is
separate from the stable release workflow and always produces a GitHub
prerelease whose tag starts with `macos-unsigned-`.

The workflow accepts one input, `source_ref`, resolves it to a full commit from
the private Tauri repository, verifies that commit, and builds native Intel and
Apple Silicon bundles. The public wrapper never uploads the private checkout,
compiler cache, debug output, or source archive.

## Published assets

Every successful release contains exactly these files:

- `FanqieNovelDownloader-macos-arm64-unsigned.dmg`
- `FanqieNovelDownloader-macos-arm64-unsigned.zip`
- `FanqieNovelDownloader-macos-x64-unsigned.dmg`
- `FanqieNovelDownloader-macos-x64-unsigned.zip`
- `SHA256SUMS-macos-unsigned.txt`

DMG is the primary installer. ZIP contains the same APP bundle for users who
cannot mount a disk image. Intermediate Actions artifacts expire after seven
days; the five release assets remain attached to the prerelease.

## Publication invariants

The unsigned channel must keep all of these properties:

- `createUpdaterArtifacts`, updater JSON upload, and updater signature upload
  are disabled.
- No `APPLE_*` certificate, identity, account, password, or team secret is
  passed to the build action.
- The APP has the expected Bundle ID, version, icon, Mach-O architecture, and
  no `_CodeSignature` directory; the DMG passes `hdiutil verify`.
- The release stays marked as a prerelease and does not become GitHub's latest
  stable release.
- Asset names include `unsigned`, and publication stops unless the exact
  expected asset set and SHA-256 manifest are present.

Do not route this workflow through `scripts/finalize-release.py`. That script
owns stable release notes and updater metadata; the unsigned channel must not
create or modify `latest.json`.

## Failure handling

The release is created as a draft only after wrapper and private-source tests
pass. Build or validation failure leaves the draft unpublished. Inspect the
failed job, rerun the workflow after fixing the cause, and delete an abandoned
draft only after confirming its tag begins with `macos-unsigned-`. Never delete
the current stable release as part of unsigned-channel cleanup.

## User installation boundary

Release notes direct users to macOS System Settings, Privacy & Security, and
Open Anyway. After verifying `SHA256SUMS-macos-unsigned.txt`, a user may remove
quarantine from this app only with:

```bash
xattr -dr com.apple.quarantine "/Applications/Fanqie Novel Downloader.app"
```

Never recommend disabling Gatekeeper globally. Formal signed and notarized
macOS publication remains the long-term stable channel.
