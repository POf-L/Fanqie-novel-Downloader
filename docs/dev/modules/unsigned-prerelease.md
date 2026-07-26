# Unsigned Tauri Prerelease

## Responsibility

`.github/workflows/build-release.yml` has a separate unsigned publication
mode for testing builds when the Tauri updater key, Android release keystore,
or Apple signing credentials are unavailable. The mode publishes a named
GitHub prerelease for manual downloads and never enters the stable updater
channel.

## Dispatch contract

Set these workflow inputs together:

- `publish_release: false`
- `publish_unsigned_prerelease: true`

The inputs are mutually exclusive. Keep `publish_unsigned_prerelease` false
for the existing signed publication path; that path keeps its original secret
checks and `v<version>` tag format. Unsigned runs use an isolated
`unsigned-v<version>-r<run_number>` tag, so a rerun cannot replace a stable tag.

From an authenticated GitHub CLI session, the essential dispatch fields are:

```powershell
gh workflow run "Build and Release Tauri" `
  -f publish_release=false `
  -f publish_unsigned_prerelease=true
```

## Build and upload flow

Unsigned mode forces `createUpdaterArtifacts` to false and does not pass Tauri,
Apple, or official Android signing secrets to build commands. Tauri action is
used only for compilation and short-lived Actions artifacts. Its release
upload is disabled because the action can package a macOS `.app` as an
`.app.tar.gz` even when updater artifacts are disabled.

The workflow then uploads only filtered installers to the draft release:

- Windows NSIS setup `.exe`
- Linux `.deb` and any native `.AppImage`
- macOS `.dmg` plus an APP `.zip`
- Android APK/AAB and iOS IPA from their existing collection steps

`finalize-unsigned` obtains GitHub SHA-256 digests, writes
`SHA256SUMS-unsigned.txt`, rejects `latest.json`, updater archives, and
signature files, and publishes the draft with `--prerelease`. It does not call
`scripts/finalize-release.py` or `scripts/normalize-updater-metadata.py`.

## Release invariants

The final notes must contain the exact warning:
`未签名版本，仅供测试，不支持自动更新`.

They also explain that Windows may show an Authenticode/SmartScreen
“未知发布者” warning, macOS may block the app with Gatekeeper because there
is no Developer ID signature or notarization, Android uses a one-off CI test
certificate, and iOS requires sideloading. The stable `releases/latest` tag is
read before and after publication and the job fails if it changes.

No unsigned release may contain `latest.json`, `.sig`, `.nsis.zip`,
`.msi.zip`, `.app.tar.gz`, or `.AppImage.tar.gz`. Users must download from the
Release Assets page and verify the unsigned checksum manifest manually.

## Failure recovery

Failures before publication leave a draft tagged `unsigned-*`. Inspect the
asset list and rerun the same dispatch after fixing the build. Do not use the
normal `Finalize Draft Release` workflow for this tag: it intentionally expects
signed updater metadata. Delete an abandoned unsigned draft only after
confirming that the current stable release tag is unchanged.
