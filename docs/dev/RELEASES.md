# Release Operations

## Asset flow

The workflow builds desktop artifacts with Tauri, uploads them to a draft
GitHub Release, and then collects Android/iOS artifacts. Tauri's generated
`latest.json` can contain GitHub API asset URLs such as
`api.github.com/repos/.../releases/assets/<id>`.

The finalization job runs
`scripts/normalize-updater-metadata.py` after every asset is present. It maps
each updater entry by asset ID, rewrites the URL to the matching
`github.com/<owner>/<repo>/releases/download/<tag>/<asset>` address, validates
all signatures and URLs, and only then publishes the release.

The dispatch form keeps platform selection in one validated `platforms` string
so it stays within GitHub's workflow input limit. Release jobs pin Rust to the
same `1.97.0` toolchain declared by the Tauri source repository.

## Local validation

```powershell
python -m unittest discover -s tests -p 'test_*.py'
python scripts/normalize-updater-metadata.py --help
```

Never add a GitHub token or updater private key to a fixture. The release job
uses its ephemeral `GITHUB_TOKEN` only through `gh api` and `gh release`.

## Repair an existing release

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
