# Security Policy

## Scope

This repository owns the published release artifacts, the update metadata
(`latest.json` and the `unsigned` update channel), the structured issue intake,
and the GitHub Actions workflows that build and publish those artifacts.

## Supported versions

We support security fixes for the latest code on the default branch and the
latest published release.

| Version | Supported |
| --- | --- |
| `main` / latest release | ✅ |
| Older releases | ⚠️ Best effort |
| Unmaintained historical versions | ❌ |

## Reporting a vulnerability

Please **do not open a public issue** for a suspected vulnerability.

Report it privately by one of the following methods:

- Open a private GitHub security advisory for this repository, if enabled.
- Contact the maintainer through the repository owner profile on GitHub.

Please include:

- A clear description of the issue
- Affected version / release tag or commit
- Reproduction steps or proof of concept
- Potential impact
- Any suggested remediation

Never paste tokens, signing keys, keystores, private keys, device identifiers,
cookies, or personal data into a public issue, log, or screenshot. Sanitize any
diagnostic material first. Revoke exposed credentials immediately: deleting a
secret in a later commit does not remove it from repository history.

## Response target

We will try to:

- acknowledge valid reports within **7 days**
- provide a remediation plan or status update as soon as practical
- release a fix after verification when the issue is confirmed

## Disclosure

Please allow reasonable time for investigation and patching before public
disclosure.
