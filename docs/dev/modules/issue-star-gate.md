# Issue Star Gate

`.github/workflows/issue-star-gate.yml` runs when an Issue is opened. It reads
the repository's public stargazer list through the GitHub REST API and compares
the Issue author's login case-insensitively.

When the author is found, the workflow leaves the Issue unchanged. When the
author is not found, it posts a comment linking to the repository, asks the
author to star the project and submit a new Issue, then closes the Issue with
the `not_planned` state reason.

The workflow has only `contents: read` and `issues: write` permissions. Errors
while reading the stargazer list fail the job before any write operation, so a
transient lookup failure does not close an Issue by mistake. A failed write is
surfaced as a failed job and can be retried from the workflow run.

GitHub's stargazer endpoint exposes public stars only. Authors who keep their
star private must make it public for this automated check to recognize it.
