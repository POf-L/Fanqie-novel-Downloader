# Developer Documentation

- [Release Operations](RELEASES.md): release asset and updater metadata rules.
- [Release Metadata Normalizer](modules/release-metadata.md): the script and
  workflow contract that makes updater URLs publicly downloadable.
- [Release Finalizer](modules/release-finalizer.md): draft validation,
  checksums, release notes, publication, and failure recovery.
- [Unsigned macOS Release](modules/macos-unsigned-release.md): isolated
  prerelease packaging for Intel and Apple Silicon without Apple credentials.
- [Unsigned Tauri Releases](modules/unsigned-prerelease.md): full-platform
  manual-download prerelease and normal-Release paths without updater or
  official signing keys.
- [Legacy Release-Note Tools](modules/legacy-release-notes.md): historical
  one-off scripts kept separate from the supported publication path.
- [Issue Star Gate](modules/issue-star-gate.md): automatic public-star checks
  for newly opened Issues.
- [Repository README](../../README.md): user-facing features and downloads.
