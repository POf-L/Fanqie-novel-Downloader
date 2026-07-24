# Release Finalizer

## Responsibility

`scripts/finalize-release.py` is the single publication entry point used by a
normal multi-platform build and by draft recovery. It changes release state;
`scripts/prepare-release-artifacts.py` is its deterministic, offline generator
for release notes and the full SHA-256 manifest.

## Inputs

The finalizer requires `GH_TOKEN`, `--repo`, and `--tag`. Normal builds also
pass the version, private source ref and commit, and selected platforms. A
recovery run may omit those optional values when the draft notes still contain
the build fields. Optional release highlights are read from a text file.

## Publication sequence

1. Resolve the tag with `gh release view`, then fetch the draft and all assets
   through the numeric Release database ID. The tag API is not used for drafts.
2. Download only `latest.json`, normalize it against the authenticated asset
   list, run `--check`, upload it, and refresh the asset metadata.
3. Generate `SHA256SUMS-release.txt` from every GitHub `sha256:` asset digest
   except the manifest itself. Generate final notes from the same asset set.
4. Upload the manifest and refetch the draft. Recheck the manifest and updater
   metadata before publishing.
5. Publish the draft. For a stable release, explicitly mark it latest, then
   verify canonical asset URLs, checksums, updater URLs, source commit, and the
   repository's latest stable release.

Any failure before step 5 leaves a recoverable draft. The finalizer rejects an
already-published release so recovery cannot silently rewrite a stable release.

## Platform status block

`scripts/prepare-release-artifacts.py` adds `平台状态与安装限制` to every
final note. The block is derived from the actual asset names and control files,
so a missing platform is called out instead of receiving a guessed download
link. It documents the current Windows Authenticode, Linux package-signing,
Android keystore, iOS sideload, macOS Developer ID/notarization, and updater
boundaries. Keep this block in the supported generator when adding a platform or
changing its signing gate; do not rely on the legacy PowerShell rewriter for
routine publication.

## Verification

`tests/test_prepare_release_artifacts.py` exercises digest manifests, tamper
detection, source build fields, and percent-encoded download links.
`tests/test_release_workflow.py` enforces the database-ID draft lookup and keeps
the recovery workflow independent from platform builds.
