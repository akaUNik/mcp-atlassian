# Changelog

## [Unreleased]

## [0.24.0-beta.2] - 2026-10-01

### Fixed

- Normalize SemVer Docker prerelease tags to PEP 440 before installing the Python
  package, so beta and release-candidate images build successfully (#3).

### Validation

- Full pytest suite: 4014 passed, 251 skipped; all pre-commit hooks passed.
- Docker version regression tests pass for stable, beta, and rc tags, with both
  initial and already versioned package fallbacks.
- Includes all PAT + mTLS functionality and validation from beta.1.
- Secret Scanning still flags the synthetic URI fixture recorded below.

## [0.24.0-beta.1] - 2026-10-01

### Added

- Jira PAT authentication with verified server TLS and PEM client certificates
  for SberWorks and other Jira Server/Data Center installations (#1).
- `JIRA_CA_CERT` for an operator-managed CA bundle, with early validation (#1).
- Scoped TLS configuration inheritance for per-request PAT authentication (#1).
- Local mTLS acceptance tests and read-only SberWorks configuration examples (#1).

### Fixed

- Pin the isolated mypy hook's Deprecated dependency to the locked version (#1).

### Changed

- Publish this fork's testing release as GitHub assets and a versioned Docker
  image; reserve PyPI publishing for stable upstream releases (#3).

### Validation

- Full pytest suite after release preparation: 4010 passed, 251 skipped.
- All repository pre-commit hooks passed, including isolated mypy.
- Live SberWorks current-user and bounded search requests returned HTTP 200 with
  server certificate verification and client certificate authentication enabled.
- Broader application-environment mypy retains 114 pre-existing diagnostics in
  unchanged FastMCP/E2E files; no new diagnostics were introduced.
- Secret Scanning flags the synthetic `user:password` URI in the URL rejection
  regression test. The release assets contain no operator PAT or local files.
