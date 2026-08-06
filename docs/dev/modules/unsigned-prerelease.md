# Unsigned Tauri Releases

## Responsibility

`.github/workflows/build-release.yml` has explicit unsigned publication modes
for testing builds when the Tauri updater key, Android release keystore, or
Apple signing credentials are unavailable. Both modes publish named GitHub
Release assets for manual downloads. Full-platform unsigned builds also use an
isolated `unsigned` updater channel whose payloads are signed by the Tauri
updater key; they never enter the signed `stable` channel.

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
gh workflow run build-release.yml `
  -f publish_release=false `
  -f publish_unsigned_prerelease=true
```

For a normal (non-prerelease) GitHub Release that becomes GitHub Latest while
remaining isolated from the signed `stable` updater channel, use the explicit
formal unsigned mode:

```powershell
gh workflow run build-release.yml `
  -f publish_release=true `
  -f publish_unsigned_release=true `
  -f prerelease=false `
  -f platforms=windows-x64,windows-arm64,linux-x64,linux-arm64,macos-x64,macos-arm64,android,ios
```

`publish_unsigned_release` is mutually exclusive with
`publish_unsigned_prerelease` and requires `publish_release=true`. The formal
unsigned Release becomes GitHub Latest for manual downloads, while signed
clients continue to read `stable/latest.json` and unsigned clients read
`unsigned/latest.json`.

## Build and upload flow

Unsigned mode still requires the Tauri updater signing key and enables
`createUpdaterArtifacts`, but it deliberately omits Windows Authenticode,
macOS Developer ID/notarization, and iOS Apple signing. The custom upload path
adds user-facing unsigned installers alongside the Minisign-protected updater
payloads, plus the `--no-sign` iOS IPA.

The workflow then uploads only filtered installers to the draft release:

- Windows NSIS setup `.exe`
- Linux `.deb` and any native `.AppImage`
- macOS `.dmg` plus an APP `.zip`
- Android APK/AAB and iOS IPA from their existing collection steps

The independently named `finalize-unsigned-release` job invokes only
`scripts/finalize-unsigned-release.py`; it does not replace or enter the signed
`finalize` job. It normalizes updater metadata, writes
`SHA256SUMS-unsigned.txt`, publishes the draft, refreshes the fixed `unsigned`
metadata alias, and appends a managed finalizer block to the original Draft
body. The block contains the actual device/architecture links and is verified
again after publication. A published Release can have only that managed block
refreshed through maintenance operation `append-unsigned-finalizer`.

## Release invariants

The notes explain that OS/vendor signing is absent while updater payloads remain
verified by the project Minisign key. They include Windows x64/ARM64, macOS
Intel/Apple Silicon, Linux x64/ARM64, every Android ABI/universal choice, and
the unsigned iOS side-loading guide. Missing device-guide headings or update
channel links are a hard finalizer failure.

They also explain that Windows may show an Authenticode/SmartScreen
“未知发布者” warning, macOS may block the app with Gatekeeper because there
is no Developer ID signature or notarization, Android uses a one-off CI test
certificate, and iOS requires sideloading. The signed `stable` alias is read
before and after publication and the job fails if its source changes. Formal
unsigned publication separately verifies GitHub Latest and the public
`unsigned/latest.json` endpoint.

Unsigned Releases contain `latest.json`, `.sig`, and updater payloads only when
the Tauri signing key is available. `latest.json` must map exclusively to assets
on the same Release and every entry must carry a signature. User-facing
installers and `SHA256SUMS-unsigned.txt` remain available for manual download
and side-loading.

## Failure recovery

发布前失败会留下 `unsigned-*` 草稿。决定是否重新构建前，先检查附件列表。如果请求的安装包
已经全部上传，运行 `release-maintenance.yml`，选择 `finalize-unsigned-draft`，并填写原 tag
和发布模式。该操作复用 `scripts/finalize-unsigned-release.py`，重新校验全部附件后直接发布，
不会重新构建。不要对该 tag 使用 `finalize-signed-draft`，因为签名路径要求 updater 元数据。
删除废弃无签名草稿前，必须再次确认当前稳定版 tag 未发生变化。
