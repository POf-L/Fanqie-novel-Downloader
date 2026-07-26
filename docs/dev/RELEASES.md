# Release Operations

## Latest Verified Release

[`v2026.7.26-709`](https://github.com/POf-L/Fanqie-novel-Downloader/releases/tag/v2026.7.26-709)
was published by Actions run
[`30192288645`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30192288645)
from private Tauri source commit `d48e82791b04dce7fee4025ee54f8b5263f3a29c`.
The release contains 24 assets for Windows x64/ARM64, Linux x64/ARM64, Android
all ABIs/AAB, and unsigned iOS, plus updater signatures, `latest.json`, and
complete SHA-256 manifests. Every build and finalization job passed, the
release is non-draft/non-prerelease, and GitHub's `releases/latest` endpoint
resolves to this tag. It includes the Android 12 WebView scrolling fix and the
device-registration fallback hosts/network diagnostics. macOS is absent from
the signed stable asset set until Developer ID signing and notarization
credentials are configured.

macOS users are served through the separate unsigned prerelease channel while
the stable release remains gated on Apple signing. Its workflow contract,
asset set, source-isolation rules, and recovery procedure are documented in
[Unsigned macOS Release](modules/macos-unsigned-release.md).

## Latest Verified Unsigned Full-Platform Release

[`unsigned-v2026.7.26-742-r635`](https://github.com/POf-L/Fanqie-novel-Downloader/releases/tag/unsigned-v2026.7.26-742-r635)
was built by Actions run
[`30193277041`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30193277041)
from wrapper commit `51af36caae8a6566261ee99dc146ac7ebaab89c9` and
private Tauri source commit `d48e82791b04dce7fee4025ee54f8b5263f3a29c`.
All Windows, Linux, macOS Intel/Apple Silicon, Android, and unsigned iOS jobs
passed. The build run's original inline publish step then failed before its API
call because a nested shell heredoc terminator was indented. Wrapper commit
`c58bcca1eee6b29d89bfb4e90f4f84729a253018` extracted the logic into
`scripts/finalize-unsigned-release.py`; recovery run
[`30195164073`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30195164073)
reused the existing draft assets and published without rebuilding.

The result is a normal GitHub Release (`draft=false`, `prerelease=false`) with
21 assets, including both macOS DMG/APP ZIP architectures and the unsigned IPA.
It is deliberately `make_latest=false`: the signed updater channel remains
`v2026.7.26-709`. The release contains no `latest.json`, updater archive, or
`.sig` asset. `SHA256SUMS-unsigned.txt` matches all 20 other GitHub asset
digests, all 21 anonymous download URLs return HTTP 200, and the notes document
Windows unknown-publisher warnings, macOS Gatekeeper handling, and iOS
AltStore/Sideloadly/TrollStore side-loading.

## Latest Verified Unsigned macOS Client

[`macos-unsigned-v2026.7.24-38-r2`](https://github.com/POf-L/Fanqie-novel-Downloader/releases/tag/macos-unsigned-v2026.7.24-38-r2)
was published as a prerelease by Actions run
[`30056768823`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30056768823)
from wrapper commit `48612d5d8c1abc1db1bcc553aaebc51cb4d5bad3`
and private Tauri source commit
`091ab8c834084c93406a6c2e33632a8278c024f0`.

Both native macOS jobs mounted their generated DMG, copied the packaged APP,
launched its executable for 15 seconds, and found no early exit, panic, or fatal
startup log. They also verified the expected Mach-O architecture, version
`2026.7.24-38`, Bundle ID, icon, executable permissions, absence of
`_CodeSignature`, and DMG integrity before publication. Post-publication HTTP
checks confirmed all four anonymous DMG/APP ZIP links and the checksum link
return 200. The exact asset set carries GitHub SHA-256 digests and a checked
release manifest. The release is non-draft and prerelease; GitHub's latest
stable release remains `v2026.7.26-709`. The superseded packaging-only r1
prerelease and tag were deleted after r2 passed.

## Asset flow

The workflow builds desktop artifacts with Tauri, uploads them to a draft
GitHub Release, and then collects Android/iOS artifacts. Tauri's generated
`latest.json` can contain GitHub API asset URLs such as
`api.github.com/repos/.../releases/assets/<id>`.

While a build is running, the draft notes temporarily link to the latest
published release. That bootstrap list includes Android `arm64-v8a`,
`armeabi-v7a`, `x86_64`, universal APK, AAB, and the unsigned iOS IPA whenever
those assets exist. Architecture-specific APKs must never be used as the
universal fallback. Finalization replaces the bootstrap links with the assets
uploaded for the new tag.

The finalization job delegates to `scripts/finalize-release.py` after every
platform job has finished. The finalizer resolves the draft to its database ID,
fetches the authenticated asset list, normalizes and re-uploads `latest.json`,
and creates `SHA256SUMS-release.txt` from GitHub's asset digests. It then
generates final Chinese release notes, including a platform status and signing
limitations block, and validates every generated artifact.
Only a fully validated draft is published. The finalizer checks the published
asset URLs, updater metadata, checksum manifest, source commit, and stable
`latest` state once more after publication.

The dispatch form keeps platform selection in one validated `platforms` string
so it stays within GitHub's workflow input limit. Release jobs pin Rust to the
same `1.97.0` toolchain declared by the Tauri source repository.

For a manual-download build without release signing credentials, dispatch the
same workflow with `publish_release=false` and
`publish_unsigned_prerelease=true` for a prerelease, or with
`publish_release=true` and `publish_unsigned_release=true` for a normal
non-prerelease Release. Both paths are intentionally separate from the signed
finalizer; their contract and forbidden asset list are documented in
[Unsigned Tauri Releases](modules/unsigned-prerelease.md). The formal unsigned
mode keeps GitHub's `latest` pointer on the signed updater release so it cannot
break automatic-update requests.

## Stable macOS publication gate

A published macOS APP/DMG must use a Developer ID certificate, complete Apple
notarization, and pass both `codesign --verify --deep --strict` and
`spctl --assess --type execute`. Selecting either macOS target while
`publish_release` is true therefore requires these repository Secrets:

- `APPLE_CERTIFICATE`
- `APPLE_CERTIFICATE_PASSWORD`
- `APPLE_SIGNING_IDENTITY`
- `APPLE_ID`
- `APPLE_PASSWORD`
- `APPLE_TEAM_ID`

The workflow checks only whether all names are configured and never prints a
value. An unsigned local test build may still run with publication disabled,
but it must not be attached to a stable release because Gatekeeper presents it
to users as damaged. The Tauri action receives Apple credentials only after
this gate succeeds; unsigned test runs leave those variables undefined so the
action does not attempt to import an empty certificate. As of 2026-07-24 these
Secrets are not configured in the public wrapper or the private source
repository, so macOS publication is intentionally blocked.

Unsigned packaging was verified on 2026-07-24 by Actions run
[`30053365281`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30053365281)
from private source commit `3eb84f3deee4bd7263c0947671e665983876b96a`.
Native Intel and Apple Silicon APP/DMG jobs, plus the Intel fallback job, all
succeeded without invoking certificate or keychain import. The four native
artifact archives matched their Actions SHA-256 digests and contained the
expected x86_64/arm64 Mach-O executable, bundle identifier, version, icon, and
DMG. They remain seven-day workflow artifacts and were not attached to a
Release.

The dedicated `Publish Unsigned macOS Client` workflow remains available for a
macOS-only smoke-test channel. The main build workflow also has explicitly
opt-in `publish_unsigned_prerelease` and `publish_unsigned_release` paths for
full-platform manual downloads; both disable updater metadata and check that
GitHub's latest stable tag remains unchanged. The formal mode is a normal
GitHub Release (not a prerelease), while still remaining outside the updater
channel. See [Unsigned macOS Release](modules/macos-unsigned-release.md) and
[Unsigned Tauri Releases](modules/unsigned-prerelease.md) for their contracts.

The first end-to-end main-workflow smoke run used private source commit
`65723ef2f763b66276053a04c69e4d59312f4281` and published the Windows-only
[`unsigned-v2026.7.26-642-r633`](https://github.com/POf-L/Fanqie-novel-Downloader/releases/tag/unsigned-v2026.7.26-642-r633)
prerelease from Actions run
[`30191501813`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30191501813).
Its installer and `SHA256SUMS-unsigned.txt` both return HTTP 200; the manifest
digest matches GitHub's asset digest, and the stable `latest` tag remains
`v2026.7.23-1739`.

## Source isolation

The public wrapper is an orchestration repository, not a mirror of the private
Tauri source. Each build job checks out the requested private commit with the
`PRIVATE_SOURCE_TOKEN` secret and `persist-credentials: false`. The checkout
exists only on the ephemeral runner; workflow artifacts and release assets are
limited to built binaries, signatures, and verification manifests. Do not add
source archives, caches, debug dumps, or source-bearing logs to the upload
steps. The public wrapper deliberately does not enable `actions/cache` or
`Swatinem/rust-cache` for private-source jobs; all compiler output remains on
the disposable runner. The two cross-job binary artifacts use a seven-day
retention window and are not part of the public release asset set.

## Draft hygiene

Each build may leave one recoverable draft when finalization fails. Keep a
draft only while it is tied to an active or intentionally recoverable Actions
run. After the run is finished, inspect the numeric release ID and delete
abandoned `untagged-*` drafts; never delete a named stable or historical
prerelease release as part of this cleanup. The current stable release must be
rechecked after any draft deletion.

An `unsigned-*` draft with complete installers is recovered through
`Finalize Unsigned Draft Release`; that workflow invokes the dedicated
unsigned finalizer and never calls the updater metadata normalizer. The signed
`Finalize Draft Release` workflow remains limited to signed `v*` drafts.

## Local validation

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python scripts/normalize-updater-metadata.py --help
python scripts/prepare-release-artifacts.py --help
python scripts/finalize-release.py --help
actionlint -no-color
```

Never add a GitHub token or updater private key to a fixture. The release job
uses its ephemeral `GITHUB_TOKEN` only through `gh api` and `gh release`.

## Recover a draft release

A failure before `gh release edit --draft=false` intentionally leaves the
release as a draft. Dispatch `Finalize Draft Release` with the existing tag to
reuse all uploaded binaries and rerun only metadata generation, validation, and
publication. The optional source fields fall back to the build information in
the draft notes. The workflow refuses an already-published release.

```powershell
$env:DRAFT_TAG = Read-Host "Existing draft tag"
gh workflow run "Finalize Draft Release" -f tag=$env:DRAFT_TAG
```

## Repair published updater metadata

The `Repair Updater Metadata` workflow can be dispatched from the Actions tab
with a release tag. Leave the tag empty to select the current stable release.
It downloads only `latest.json`, resolves its asset IDs with the authenticated
GitHub API, validates public browser URLs, and uploads the corrected metadata
without rebuilding the binaries.

From an authenticated local GitHub CLI session, the same repair can be started
with:

```powershell
gh workflow run "Repair Updater Metadata" -f tag=v2026.7.21-1511
```
