# Tasks

## 1. Jira CA configuration

- [x] 1.1 Add optional `ca_cert` to `JiraConfig` and load `JIRA_CA_CERT`, treating blank environment values as unset; add tests in `tests/unit/jira/test_config.py` verifying PAT precedence, Server/DC detection for the SberWorks URL, and unchanged boolean SSL parsing.
- [x] 1.2 Validate explicit CA configuration for readable PEM files and conflicts with disabled verification, including programmatic configs; verify missing, unreadable, malformed, and conflicting settings fail before an authenticated request without logging credentials.
- [x] 1.3 Add the variable and its conflict/default semantics to `.env.example` and `docs/configuration.mdx`; verify documented names and defaults match the config tests.

## 2. Jira TLS transport and API paths

- [x] 2.1 Extend the shared SSL helper with a backward-compatible optional trailing CA argument and configure explicit session verification; extend `tests/unit/utils/test_ssl.py` to verify CA plus combined PEM, separate keys, NO_PROXY, and existing no-CA/Confluence behavior.
- [x] 2.2 Align Atlassian-client and session verification/certificate settings in `jira/client.py`; extend `tests/unit/jira/test_client.py` using the real Atlassian client with a recording transport to verify outgoing Bearer authorization, CA and cert values for both API and direct-session calls, while PAT still disables `trust_env`.
- [x] 2.3 Add regression coverage for current-user, issue, and bounded-search URLs with `/jira` and `/jira/` base forms; verify all generated REST paths retain the context exactly once, and change path construction only if a regression is demonstrated.
- [x] 2.4 Extend existing proxy/PAC and SSL adapter tests to verify CA/client-certificate state survives session conversion and NO_PROXY routing, while SSRF hooks, pinning, and HTTP hardening remain present; run affected tests in `tests/unit/utils/test_proxy.py` and `tests/unit/jira/test_client.py`.
- [x] 2.5 Update `docs/authentication.mdx` and `docs/troubleshooting.mdx` with PAT plus mTLS and explicit Jira CA guidance; verify examples retain `JIRA_SSL_VERIFY=true` and accurately describe combined PEM and encrypted-key limitations.

## 3. HTTP per-request Jira clients

- [x] 3.1 Extend Jira header-PAT network resolution in `servers/dependencies.py` to inherit operator CA/cert/key settings only for the configured instance; verify global-config and environment-fallback cases in `tests/unit/servers/test_dependencies.py`, with the user's request PAT preserved.
- [x] 3.2 Cover parsed URL equivalence and certificate isolation with dependency regression tests; verify trailing slash, hostname case, and default HTTPS port equivalents inherit settings, while different hosts, schemes, ports, paths, userinfo, or query/fragment forms do not inherit certificate identity.
- [x] 3.3 Verify the existing `dataclasses.replace` per-user path retains Jira CA and certificate fields and that Confluence/header-PAT defaults remain unchanged; run the relevant dependency tests without adding certificate-path request headers.
- [x] 3.4 Update `docs/http-transport.mdx` with operator-managed TLS inheritance and target matching rules; verify the documented header-PAT example uses the existing supported headers and explains instance-specific certificate scope.

## 4. End-to-end transport acceptance

- [x] 4.1 Add deterministic local TLS coverage in `tests/integration/test_ssl_verification.py` using generated test CA/server/client certificates and a server requiring mTLS; verify an API request under `/jira/` and a direct session request succeed with PAT plus CA plus PEM, and fail with missing client identity, wrong CA, or hostname mismatch without disabling TLS verification.
- [x] 4.2 Complete the SberWorks MCP configuration example in `docs/configuration.mdx` and read-only smoke procedure in `docs/troubleshooting.mdx`, including container certificate mounts; verify JSON syntax and that all example environment names exist, and use placeholder tokens and generic certificate paths in public docs.
- [x] 4.3 Run the full applicable pytest suite and repository Ruff/mypy checks using `uv`, recording results and any environment-only limitations; verify no existing Jira or Confluence auth regressions. Regenerate tool docs only if implementation changes tool signatures or registrations.
- [x] 4.4 With operator credentials and network access available, run a read-only SberWorks current-user request plus a permitted issue fetch or bounded search using the supplied combined PEM and CA; record authenticated results separately from the unauthenticated gateway 401 observed during planning, or record the precise missing credential/access limitation without claiming live compatibility.

## Validation notes

- Live SberWorks validation on 2026-10-01: passed using the operator PAT
  read from the local `.env.pat` file, the supplied combined client PEM, and
  the supplied CA PEM. `JIRA_SSL_VERIFY=true` and `READ_ONLY_MODE=true` were
  retained. The real JiraClient made GET `/jira/rest/api/2/myself` (HTTP 200,
  authenticated current-user identity returned) and GET
  `/jira/rest/api/2/search` with `maxResults=1` (HTTP 200, one issue returned).
  Both responses were JSON. No Jira data was modified. This confirms
  authenticated read-only API access for the tested operator configuration;
  the unauthenticated gateway 401 observed during planning is separate evidence.
  Real PAT values, user identities, issue contents and certificate contents
  are not recorded in these artifacts.
- Locked dependencies installed with `uv sync --frozen --all-extras --dev
  --no-install-package uv`; the already-running uv executable was reused after
  slow downloads. Checks used `uv run --no-sync` against that environment.
- Focused Jira/config/SSL/proxy/dependency tests and local TLS integration:
  279 passed, 2 environment-dependent skips (`--integration`). All eight local
  mTLS API/direct-session success and rejection scenarios passed with server
  verification enabled and the application's default truststore client stack.
- Full repository pytest: 4008 passed, 251 skipped, 14 warnings. Skips include
  environment-dependent real-service/integration tests; transport lifecycle
  mock tests emit existing unawaited-coroutine warnings.
- Repository Ruff check with `.pre-commit-config.yaml` ignore options: passed.
  Ruff format check on all 14 changed Python files: passed.
- Repository mypy using explicit file inputs (directory discovery excludes
  `src/`) and the pre-commit options: 114 errors in 9 unchanged files. An
  archived HEAD baseline produces the exact same 114 errors plus one SSL
  adapter override error fixed by this change. Diagnostic-set comparison:
  no added errors, one removed error. Existing FastMCP/E2E typing errors remain;
  this broader mypy invocation is not clean. The repository's isolated
  pre-commit mypy hook is a separate check.
- Release preparation: all repository pre-commit hooks passed, including
  isolated mypy (290 source files). Pinned the hook's Deprecated dependency
  to 1.3.1, matching uv.lock, because mypy 1.8 cannot parse Deprecated 3.0.
  Corrected the test CA import for the hook's requests stubs and annotated
  the HTTP test handler's required do_GET name for Ruff 0.9.7. Rechecked the
  affected client/SSL tests and local mTLS integration: 85 passed, 2 skipped.
- Configuration and HTTP-transport JSON examples parse successfully; the
  SberWorks example's environment names exist in source configuration.
  `openspec validate add-sberworks-jira-pat-mtls --strict` and `git diff --check`
  pass. No tool signatures or registrations changed, so tool docs do not need
  regeneration.
