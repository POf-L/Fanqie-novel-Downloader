# Release Operations

## Latest Verified Release

[`v2026.7.23-1739`](https://github.com/POf-L/Fanqie-novel-Downloader/releases/tag/v2026.7.23-1739)
was published by Actions run
[`30030326151`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30030326151)
from private Tauri source commit `742ef58639200e891e2f80e8129173e2dac5b87f`.
The release contains 26 assets, 12 working user download links for Windows,
Linux, Android and unsigned iOS, complete SHA-256 manifests, and canonical
updater URLs. macOS is intentionally absent until Developer ID signing and
notarization credentials are configured. The build and release jobs passed;
Android 14 API 34 emulator tap-through has also passed, including a real SAF
directory export. OEM document providers and physical display cutouts remain
separate device checks.

macOS users are served through the separate unsigned prerelease channel while
the stable release remains gated on Apple signing. Its workflow contract,
asset set, source-isolation rules, and recovery procedure are documented in
[Unsigned macOS Release](modules/macos-unsigned-release.md).

## Latest Verified Unsigned macOS Client

[`macos-unsigned-v2026.7.24-22-r1`](https://github.com/POf-L/Fanqie-novel-Downloader/releases/tag/macos-unsigned-v2026.7.24-22-r1)
was published as a prerelease by Actions run
[`30056011403`](https://github.com/POf-L/Fanqie-novel-Downloader/actions/runs/30056011403)
from wrapper commit `c708ecae3e9af406f169b46099835e30521ba8bd`
and private Tauri source commit
`091ab8c834084c93406a6c2e33632a8278c024f0`.

Post-publication verification confirmed all four anonymous DMG/APP ZIP links
and the checksum link return HTTP 200. Downloaded files match both the release
manifest and GitHub's SHA-256 digests. The APP ZIPs contain executable arm64
and x86_64 Mach-O binaries, version `2026.7.24-22`, the expected Bundle ID and
icon, executable permissions, and no `_CodeSignature` directory. The workflow
also ran `hdiutil verify` on both DMGs before publication. The release is
non-draft and prerelease; GitHub's latest stable release remains
`v2026.7.23-1739`.

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
generates final Chinese release notes and validates every generated artifact.
Only a fully validated draft is published. The finalizer checks the published
asset URLs, updater metadata, checksum manifest, source commit, and stable
`latest` state once more after publication.

The dispatch form keeps platform selection in one validated `platforms` string
so it stays within GitHub's workflow input limit. Release jobs pin Rust to the
same `1.97.0` toolchain declared by the Tauri source repository.

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

The verified packaging path is now implemented as the dedicated `Publish
Unsigned macOS Client` workflow. It publishes only a clearly labeled
prerelease and checks that GitHub's latest stable tag remains unchanged. See
[Unsigned macOS Release](modules/macos-unsigned-release.md) for its complete
contract; do not weaken this stable signing gate to publish unsigned assets.

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
