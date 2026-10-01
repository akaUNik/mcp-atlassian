# Proposal

## Why

The MCP server needs to access Jira at `https://sberworks.ru/jira/` using a
PAT together with a client certificate and a supplied trusted CA bundle.
PAT plus client PEM already works in the global client, but there is no
explicit Jira CA-bundle setting, and header-based HTTP clients currently
omit the operator's client-certificate settings.

## What Changes

- Add optional `JiraConfig.ca_cert` and `JIRA_CA_CERT` for explicit server
  certificate verification while preserving boolean `JIRA_SSL_VERIFY`.
- Support the supplied combined PEM and CA bundle together with
  `JIRA_PERSONAL_TOKEN`; retain PAT authentication precedence and the
  existing unencrypted-private-key requirement.
- Preserve the `/jira/` context path in Jira API URLs, with regression
  coverage for trailing-slash and non-trailing-slash base URLs.
- Carry operator-managed CA and client-certificate settings into HTTP
  per-request Jira clients for the configured instance, without sending
  the operator's client certificate to a caller-selected unrelated instance.
- Keep TLS hostname and certificate verification enabled for the SberWorks
  configuration. Reject a configured CA bundle combined with explicitly
  disabled verification, and report invalid CA configuration clearly.
- Document a PAT plus mTLS MCP configuration, container path requirements,
  and a read-only live validation procedure.

## Capabilities

### New Capabilities

- `jira-pat-mtls`: Jira PAT plus client-certificate transport with an
  explicit CA bundle, context-path preservation, and consistent settings
  for global and per-request MCP clients.

### Modified Capabilities

None. The project currently has no main capability specifications.

## Impact

- Jira configuration and client setup in `src/mcp_atlassian/jira/`, the shared
  SSL helper, and Jira network-setting resolution in server dependencies.
- Existing SSL, Jira config/client, dependency, proxy, and integration tests;
  operator documentation in `.env.example` and `docs/`.
- No new MCP tools, tool-signature changes, dependencies, or version bump.
  Confluence behavior and existing Jira setups remain compatible when
  `JIRA_CA_CERT` is absent.
- GitHub issue: https://github.com/akaUNik/mcp-atlassian/issues/1.
  Planning branch: `feature/1-sberworks-pat-mtls`, based on `develop`.
- Live SberWorks compatibility remains to be confirmed with operator
  credentials. A repeated unauthenticated HTTPS HEAD request reached the
  gateway and returned HTTP 401 with a Basic challenge; this does not
  establish authenticated Jira API compatibility. Certificate contents and
  actual PAT values stay outside Git.
