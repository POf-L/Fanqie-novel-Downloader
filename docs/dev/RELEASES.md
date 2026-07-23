# Release Operations

## Asset flow

The workflow builds desktop artifacts with Tauri, uploads them to a draft
GitHub Release, and then collects Android/iOS artifacts. Tauri's generated
`latest.json` can contain GitHub API asset URLs such as
`api.github.com/repos/.../releases/assets/<id>`.

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

## Source isolation

The public wrapper is an orchestration repository, not a mirror of the private
Tauri source. Each build job checks out the requested private commit with the
`PRIVATE_SOURCE_TOKEN` secret and `persist-credentials: false`. The checkout
exists only on the ephemeral runner; workflow artifacts and release assets are
limited to built binaries, signatures, and verification manifests. Do not add
source archives, caches, debug dumps, or source-bearing logs to the upload
steps.

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
gh workflow run "Finalize Draft Release" -f tag=v2026.7.23-524
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
