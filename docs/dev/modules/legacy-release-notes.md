# Legacy Release-Note Tools

## Scope

`scripts/update-draft-notes.ps1` and `scripts/rewrite-release-notes.ps1` are
historical, manually run utilities. No GitHub Actions workflow invokes them.
They can rewrite multiple existing Releases, so they are intentionally outside
the supported publication path.

## Supported path

Use `scripts/finalize-release.py` through the build or draft-recovery workflow
for normal publication. It validates one draft, its assets, updater metadata,
checksums, and final stable state without rewriting unrelated Releases.

## Handling

Keep the legacy scripts only for deliberate historical recovery. Review the
target release list and generated request body before running either script;
never use them as part of a routine build or Issue response.
