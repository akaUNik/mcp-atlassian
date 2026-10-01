# Spec Delta

## Purpose

Enable MCP clients to access Jira Server/Data Center through PAT authorization
and mutual TLS using an explicit trusted CA bundle, including Jira instances
served under a context path such as SberWorks at `/jira/`.

## ADDED Requirements

### Requirement: PAT and client certificate work together

The server SHALL support Jira PAT authorization together with a client
certificate. When both `JIRA_PERSONAL_TOKEN` and `JIRA_CLIENT_CERT` are set,
the outbound Jira request MUST retain the PAT authorization and use the
configured certificate for TLS client authentication. A client certificate
MUST NOT replace or suppress a configured PAT.

#### Scenario: PAT plus combined PEM
- **WHEN** a Server/DC instance is configured with a PAT and a combined PEM
  containing a client certificate and its unencrypted private key
- **THEN** Jira requests use Bearer authorization for the PAT and present the
  configured client certificate during the TLS handshake
- **AND** neither a Jira username nor a Jira API token is required

#### Scenario: Separate certificate and private key
- **WHEN** a PAT, client certificate, and matching separate unencrypted
  private key are configured
- **THEN** Jira requests use the PAT together with that certificate/key pair

### Requirement: Explicit trusted CA bundle

The server SHALL accept optional `JIRA_CA_CERT` as the path to a readable
PEM CA bundle. With this setting, all outbound requests through the Jira
transport MUST use the configured CA trust material and MUST retain server
certificate and hostname verification, independently of environment trust
settings ignored by PAT authentication.

#### Scenario: SberWorks transport configuration
- **WHEN** Jira is configured with `JIRA_URL=https://sberworks.ru/jira/`, a PAT,
  `JIRA_CLIENT_CERT` pointing to a combined client PEM, `JIRA_CA_CERT` pointing
  to the operator's trusted CA PEM, and `JIRA_SSL_VERIFY=true`
- **THEN** API requests and direct session requests use the configured CA
  bundle and client certificate with the PAT
- **AND** hostname and certificate verification remain enabled

#### Scenario: Invalid CA bundle
- **WHEN** an explicit CA bundle is missing, unreadable, or not a valid PEM
  CA bundle
- **THEN** initialization of the Jira client fails with an error identifying
  the CA setting before sending an authenticated request
- **AND** the error does not include PAT or private-key contents

#### Scenario: Contradictory verification settings
- **WHEN** `JIRA_CA_CERT` is configured and `JIRA_SSL_VERIFY` explicitly
  disables verification
- **THEN** initialization fails with a configuration error explaining the
  conflict rather than silently ignoring the CA setting

#### Scenario: Server certificate validation failure
- **WHEN** a Jira server presents an untrusted, expired, or hostname-mismatched
  certificate with verification enabled
- **THEN** the connection fails with a TLS error and does not retry using
  disabled certificate verification

### Requirement: Jira context path is preserved

The server SHALL preserve the configured Jira context path when constructing
relative REST API URLs. A trailing slash on the base URL MUST NOT cause the
context path to be dropped or duplicated.

#### Scenario: SberWorks base URL with either slash form
- **WHEN** the configured base URL is `https://sberworks.ru/jira/` or
  `https://sberworks.ru/jira` and the current-user API is requested
- **THEN** the request targets
  `https://sberworks.ru/jira/rest/api/2/myself`

### Requirement: Operator TLS settings survive MCP transport selection

The server SHALL retain operator-managed Jira CA, client certificate, and
private-key settings in global clients and clients created for individual
HTTP requests to the configured Jira instance. HTTP callers MUST NOT supply
or replace certificate file paths through request headers. Operator-specific
CA and client-certificate settings MUST NOT be inherited by header-based
clients targeting a different Jira instance.

#### Scenario: Per-request PAT for the configured Jira instance
- **WHEN** an HTTP request selects the operator-configured Jira base URL and
  supplies a user PAT through the existing supported headers
- **THEN** the Jira client uses the user PAT together with the operator's CA
  bundle and client certificate
- **AND** it retains those settings even when created from environment
  network settings without a global Jira configuration object

#### Scenario: Caller selects an unrelated instance
- **WHEN** a header-based HTTP request selects a different scheme, host,
  effective port, or context path from the operator-configured Jira instance
- **THEN** that Jira client does not inherit the operator-specific CA bundle
  or client-certificate/key settings
- **AND** existing URL validation and SSRF restrictions still apply

#### Scenario: Equivalent configured URLs
- **WHEN** the operator URL and request URL differ only in hostname case,
  an explicit default HTTPS port, or a trailing slash
- **THEN** they are treated as the same Jira instance for TLS inheritance

#### Scenario: Proxy routing and direct session calls
- **WHEN** a configured Jira client uses explicit proxy settings, proxy
  bypass, or PAC routing and performs an API call or direct attachment request
- **THEN** the selected CA bundle, client certificate, and PAT remain applied
- **AND** existing SSRF and redirect protections remain active

### Requirement: Existing authentication and TLS configurations remain compatible

The server SHALL preserve existing Jira auth precedence and boolean
`JIRA_SSL_VERIFY` behavior when `JIRA_CA_CERT` is absent. Existing Cloud,
Server/DC PAT, Basic, OAuth, and certificate-only configurations MUST remain
supported. Confluence configuration behavior MUST remain unchanged.

#### Scenario: Existing Jira configuration without explicit CA
- **WHEN** a previously supported Jira configuration omits `JIRA_CA_CERT`
- **THEN** authentication selection and certificate trust behavior remain
  compatible with the existing configuration

#### Scenario: Encrypted private key remains unsupported
- **WHEN** client-certificate authentication is configured with a nonempty
  `JIRA_CLIENT_KEY_PASSWORD`
- **THEN** initialization retains the existing unsupported-key error

#### Scenario: Confluence configuration
- **WHEN** Confluence is configured alongside Jira using existing settings
- **THEN** the addition of `JIRA_CA_CERT` does not change Confluence TLS
  configuration or authentication selection

### Requirement: Operators can configure and validate SberWorks access

Documentation SHALL provide a complete MCP environment configuration for
SberWorks using PAT plus a combined client PEM and CA bundle with verification
enabled. It SHALL explain host versus container certificate paths and a
read-only validation procedure without storing actual credentials in Git.

#### Scenario: Operator follows the configuration example
- **WHEN** an operator supplies a valid PAT, accessible certificate paths,
  and network access to SberWorks
- **THEN** the documented validation checks the current user and a permitted
  issue or bounded issue search without modifying Jira data
- **AND** a TLS failure is distinguished from HTTP authentication failure
  without exposing PAT or private-key contents
