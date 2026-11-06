# 4. Verification

Each requirement is maintained under version control in `docs/srs/` of the repository `normly/web-app` on GitHub. Implementation and acceptance are tracked via GitHub issues and pull requests; by using methods from agile software development, each requirement can be monitored and “accepted”.

## REQ-SEC-001 — Encryption of data at rest

Verify encryption for production, operational, shared, and other persisted
storage, including databases, object storage, indexes, logs, and backups. The
security audit must separately verify that the only unencrypted local-data
scope is the limited authorized corpus in the private `web-app-raw-data`
submodule and artifacts directly derived by explicit local tests on
contributor-controlled developer machines in Europe. Confirm that those tests
are excluded from CI and that corpus/derived content is not written to logs,
public or production artifacts, production, or backups. This exception does
not waive source registration, legal-basis, or processing-rights checks.
