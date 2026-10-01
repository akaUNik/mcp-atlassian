# Design

## Context

See `proposal.md` for motivation and `specs/jira-pat-mtls/spec.md` for the
behavior contract. The implementation already has most of the required
transport support:

- `jira/config.py` selects PAT before certificate-only auth on Server/DC and
  reads `JIRA_CLIENT_CERT`, `JIRA_CLIENT_KEY`, and the unsupported key password.
  There is no `ca_cert` field; `ssl_verify` and `verify_ssl` are booleans.
- `jira/client.py` builds the PAT client with the configured base URL, then
  applies `configure_ssl_verification`. It sets `trust_env=False` to prevent
  `.netrc` from replacing explicit authorization.
- `utils/ssl.py` configures combined PEM or separate cert/key session state,
  SSL-ignore and NO_PROXY adapters, but does not configure an explicit CA.
- `utils/proxy.py` already copies session `verify`, `cert`, and `trust_env`
  when upgrading to PACSession. SSRF pinning and HTTP hardening are mounted
  after SSL setup; this ordering must survive.
- `_get_header_pat_network_config` in `servers/dependencies.py` copies SSL
  and proxy settings but omits certificates. The other per-user path uses
  `dataclasses.replace`, which already retains unmodified config fields.
- `tests/integration/test_ssl_verification.py` explicitly checks that a CA
  path placed in `JIRA_SSL_VERIFY` becomes boolean True. The new setting
  must not repurpose that existing variable.
- `uv.lock` pins `atlassian-python-api` 4.0.7. Its REST client explicitly
  passes `verify=self.verify_ssl` to session requests and keeps `self.cert`
  separately. Its URL joiner preserves the base context path.
- Existing authentication/configuration docs describe certificate-only auth
  and suggest disabled verification for private CAs. Add an explicit verified
  PAT plus mTLS example and update that advice for Jira.

The server gateway was reachable on 2026-09-30 through an unauthenticated
HEAD request, returning HTTP 401 with a Basic challenge. No PAT or private
certificate was used. The Jira API version and successful PAT plus mTLS
access are not established by that response; standard Server/DC API
compatibility is the integration assumption to validate during apply.

## Goals / Non-Goals

**Goals:**

- Resolve one effective TLS verification setting for both Atlassian API calls
  and direct Jira session calls, independent of `trust_env`.
- Keep credentials and TLS file paths operator-controlled, with matching
  instance checks before HTTP clients inherit certificate identity.
- Verify real transport behavior using synthetic credentials and test CAs.

**Non-Goals:**

- New SberWorks-specific APIs, browser login, gateway Basic credentials, or
  host-name special cases in production code.
- Encrypted key support, TLS algorithm changes, or certificate installation
  into the OS trust store.
- New Confluence CA environment settings or new certificate request headers.
- Tool changes, automatic Jira mutations, or committing user certificate
  contents and real tokens.

## Decisions

### 1. Add a separate optional CA setting

Add `ca_cert: str | None = None` to `JiraConfig`, read `JIRA_CA_CERT` in
`from_env`, and normalize blank environment values to unset. Keep
`ssl_verify` and the legacy `verify_ssl` property boolean. The effective
Requests verification value is the CA path when supplied, otherwise the
existing boolean.

Validate a supplied bundle before authenticated requests: ensure it is a
readable regular PEM file and can be loaded as CA trust material. Reject
`ca_cert` combined with `ssl_verify=False`. Raise a specific configuration
error naming `JIRA_CA_CERT`, catching file-access and SSL parsing errors
without including file contents or credentials. Apply the same validation
to programmatic configuration through client transport setup.

Alternative: permit a path in `JIRA_SSL_VERIFY`. Rejected because it changes
existing parsing, config types, CLI expectations, and integration-test
contracts. Alternative: rely on `REQUESTS_CA_BUNDLE` or OS installation.
Explicit service configuration is reproducible with PAT's `trust_env=False`
and does not require machine-wide installation.

### 2. Align API and session TLS state

Extend `configure_ssl_verification` with an optional trailing `ca_cert`
parameter, retaining existing positional call compatibility. Configure
`session.verify` from the CA bundle when supplied and keep the existing
certificate setup. Preserve unchanged no-CA behavior for Confluence and
existing Jira clients.

In `JiraClient`, align the Atlassian `verify_ssl` value with the same effective
CA-or-boolean setting and ensure its client-certificate state is consistent
with the session. Account for the Atlassian library's explicit per-request
arguments; test the outgoing adapter parameters, not only constructor mocks.
Complete this before validation requests, proxy conversion, or normal tool
operations. Keep `trust_env=False` for PAT and retain Bearer authorization.

Alternative: set only `session.verify`. Rejected because library API calls
explicitly pass their own boolean value. Alternative: replace all adapters
with a new custom TLS context. Unnecessary; existing Requests and pinned
adapters accept CA paths and certificates while preserving SSRF controls.

No domain-specific trust exception is added. Truststore injection remains
enabled by default; the explicit bundle adds available trust material within
the existing TLS stack. The feature does not promise an exclusive trust
allowlist when OS trust integration is active.

### 3. Inherit identity only for the configured Jira instance

Extend Jira header-PAT network resolution with the operator's `ca_cert`,
`client_cert`, `client_key`, and `client_key_password` only when the requested
base URL matches the operator base URL. Compare parsed HTTPS scheme,
case-insensitive hostname, effective port, and context path after removing
trailing slashes; compare context paths exactly and reject URL userinfo,
query/fragment tricks from the equivalence check. Never use string-prefix
host matching. Existing URL/SSRF validation still decides whether a different
target is permitted.

Use `full_jira_config` when available; otherwise read the operator base URL
and TLS settings from `JIRA_*` environment variables. If no operator URL
exists, do not inherit certificate identity. No caller header specifies a
certificate path. An unrelated allowed instance retains its existing
SSL/proxy policy and does not inherit instance-specific CA or certificate
settings. Keep Confluence's existing network resolution unchanged.

The `dataclasses.replace` path already preserves Jira fields; add regression
coverage rather than duplicating all fields. PAC conversion already preserves
session state and likewise needs verification rather than redesign.

Alternative: blindly inherit certificate paths for every header URL.
Rejected because callers choose that URL and could select another instance.

### 4. Preserve the Jira context path through the existing client

Continue passing `https://sberworks.ru/jira/` directly as the configured
Server/DC base URL, with no provider-specific URL rewriting. Tests with the
locked Atlassian client assert `/jira/rest/api/2/myself`, issue retrieval,
and search URLs for both base slash forms. Only fix a demonstrated local
path-construction regression during apply; upstream's joiner already keeps
the context path.

Alternative: strip `/jira/` or use origin-only transport URLs. Rejected because
the context identifies the Jira application behind the gateway.

### 5. Document an environment-based MCP configuration

Use the project's existing configuration surface. The user's `client_cert`
and `ca_cert` concepts map to dataclass fields and these environment variables:

```json
{
  "mcpServers": {
    "sberworks-jira": {
      "command": "uv",
      "args": [
        "--directory", "/Users/dmitry/Projects/mcp-atlassian",
        "run", "mcp-atlassian"
      ],
      "env": {
        "JIRA_URL": "https://sberworks.ru/jira/",
        "JIRA_PERSONAL_TOKEN": "<PAT supplied locally>",
        "JIRA_CLIENT_CERT": "/Users/dmitry/.certs/23722808-combined.pem",
        "JIRA_CA_CERT": "/Users/dmitry/.certs/russian-trusted-ca.pem",
        "JIRA_SSL_VERIFY": "true",
        "READ_ONLY_MODE": "true"
      }
    }
  }
}
```

This example becomes usable after implementation. It assumes the combined
PEM includes an unencrypted private key, as required by the current transport.
Public docs use generic `/etc/mcp-atlassian/` paths; local macOS paths are
recorded here as the requested operator configuration. Containers need
read-only certificate mounts and paths inside the container. `READ_ONLY_MODE`
is a validation setting; existing write tools remain available when it is
disabled and the Jira account has permission.

Alternatives: introduce a new JSON configuration parser or additional CLI
flags. Rejected because the MCP client already supplies environment variables.

## Risks / Trade-offs

- [Gateway may demand more than PAT plus mTLS] → Verify current-user REST
  access with the operator configuration; a Basic challenge without
  credentials is not evidence that a second auth scheme is required. Record
  gateway incompatibility explicitly rather than adding a silent workaround.
- [Expired certificate, encrypted key, or incomplete CA chain] → Retain
  current encrypted-key errors, validate CA loading, and distinguish TLS
  failures from HTTP 401/403 during live validation.
- [Library request arguments override session defaults] → Check API and
  direct-session adapter parameters and use a local TLS server requiring
  a synthetic client certificate.
- [New CA validation affects shared helper callers] → Keep the new parameter
  optional and verify existing Confluence and no-CA Jira behavior.
- [Per-request certificate identity crosses instance boundaries] → Test
  hostname, port, scheme, and context-path mismatches as well as equivalent
  trailing-slash/default-port forms.
- [Proxy/PAC or adapter changes lose TLS state] → Extend existing proxy and
  dependency regression coverage while preserving mount order and hooks.
- [Public CI has no SberWorks credentials] → Run deterministic local TLS
  regressions in CI and keep live read-only verification operator-run.

## Migration Plan

1. Implement the optional configuration and transport changes on the issue
   branch, add regression coverage, and update existing operator docs.
2. Run relevant tests, Ruff and mypy; review the resulting PR targeting
   `develop`. No version bump is needed for the feature branch.
3. Deploy the updated MCP server and set `JIRA_CA_CERT` alongside the PAT and
   combined PEM. Check current user and a permitted issue or bounded search
   under `READ_ONLY_MODE=true`; record whether validation succeeded.
4. Roll back by reverting the feature through a PR and removing the newly
   added variable. Previous configurations without that variable remain
   valid. SberWorks may again lack required explicit CA support after rollback.

## References

- [Requests TLS verification and client certificates](https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification).
- [Locked Atlassian REST client 4.0.7](https://github.com/atlassian-api/atlassian-python-api/blob/4.0.7/atlassian/rest_client.py).
- [Issue #1](https://github.com/akaUNik/mcp-atlassian/issues/1).
