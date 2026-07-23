# Contributing

This public repository owns Issues, release notes, and GitHub Actions packaging.
Application behavior belongs in the private Tauri source repository and is
checked out by the release workflow; do not copy application source here.

For an issue, include the release version, platform/architecture, reproduction
steps, and a sanitized log or screenshot. For official API JSON errors, keep the
diagnostic fields showing the endpoint path, HTTP status, Content-Type, and
short body preview; remove query strings, signatures, tokens, and device IDs.
For a workflow change, add or update an automated fixture and run the local
Python tests.

Never commit release credentials, updater keys, private source snapshots, or
downloaded artifacts. See `SECURITY.md` before reporting a sensitive problem.
