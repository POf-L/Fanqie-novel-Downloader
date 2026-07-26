# Unsigned Tauri Releases

## Responsibility

`.github/workflows/build-release.yml` has explicit unsigned publication modes
for testing builds when the Tauri updater key, Android release keystore, or
Apple signing credentials are unavailable. Both modes publish named GitHub
Release assets for manual downloads and never enter the updater channel.

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

For a normal (non-prerelease) GitHub Release that is still excluded from the
stable `latest` pointer, use the explicit formal unsigned mode:

```powershell
gh workflow run "Build and Release Tauri" `
  -f publish_release=true `
  -f publish_unsigned_release=true `
  -f prerelease=false `
  -f platforms=windows-x64,windows-arm64,linux-x64,linux-arm64,macos-x64,macos-arm64,android,ios
```

`publish_unsigned_release` is mutually exclusive with
`publish_unsigned_prerelease`, requires `publish_release=true`, and keeps the
GitHub `latest` pointer on the signed updater release. This prevents existing
clients from requesting a missing `latest.json` while still making the
ordinary Release page and all assets publicly downloadable.

## Build and upload flow

Unsigned mode forces `createUpdaterArtifacts` to false and does not pass Tauri,
Apple, or official Android signing secrets to build commands. Tauri action is
used only for compilation and short-lived Actions artifacts. Its release
upload is disabled because the action can package a macOS `.app` as an
`.app.tar.gz` even when updater artifacts are disabled. The custom upload path
includes unsigned macOS APP/DMG bundles and the `--no-sign` iOS IPA, so users
can install them with the documented Gatekeeper/side-loading steps.

The workflow then uploads only filtered installers to the draft release:

- Windows NSIS setup `.exe`
- Linux `.deb` and any native `.AppImage`
- macOS `.dmg` plus an APP `.zip`
- Android APK/AAB and iOS IPA from their existing collection steps

`finalize-unsigned` obtains GitHub SHA-256 digests, writes
`SHA256SUMS-unsigned.txt`, rejects `latest.json`, updater archives, and
signature files, and publishes the draft either as a prerelease or as a
normal Release according to the selected mode. It does not call
`scripts/finalize-release.py` or `scripts/normalize-updater-metadata.py`.

## Release invariants

The prerelease notes contain the exact warning
`未签名版本，仅供测试，不支持自动更新`; the formal unsigned notes contain
`未签名版本，不支持自动更新`.

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
asset list before deciding whether another build is needed. If every requested
installer is already attached, dispatch `Finalize Unsigned Draft Release` with
the existing tag and the original mode; it reuses
`scripts/finalize-unsigned-release.py`, revalidates every asset and publishes
without rebuilding. Do not use the normal `Finalize Draft Release` workflow
for this tag: it intentionally expects signed updater metadata. Delete an
abandoned unsigned draft only after confirming that the current stable release
tag is unchanged.
