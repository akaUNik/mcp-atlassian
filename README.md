# MCP Atlassian

![PyPI Version](https://img.shields.io/pypi/v/mcp-atlassian)
![PyPI - Downloads](https://img.shields.io/pypi/dm/mcp-atlassian)
![PePy - Total Downloads](https://static.pepy.tech/personalized-badge/mcp-atlassian?period=total&units=international_system&left_color=grey&right_color=blue&left_text=Total%20Downloads)
[![Run Tests](https://github.com/sooperset/mcp-atlassian/actions/workflows/tests.yml/badge.svg)](https://github.com/sooperset/mcp-atlassian/actions/workflows/tests.yml)
![License](https://img.shields.io/github/license/sooperset/mcp-atlassian)
[![Docs](https://img.shields.io/badge/docs-mintlify-blue)](https://mcp-atlassian.soomiles.com)

Model Context Protocol (MCP) server for Atlassian products (Confluence and Jira). Supports both Cloud and Server/Data Center deployments.

https://github.com/user-attachments/assets/35303504-14c6-4ae4-913b-7c25ea511c3e

<details>
<summary>Confluence Demo</summary>

https://github.com/user-attachments/assets/7fe9c488-ad0c-4876-9b54-120b666bb785

</details>

## Quick Start

### 1. Get Your API Token

Go to https://id.atlassian.com/manage-profile/security/api-tokens and create a token.

> For Server/Data Center, use a Personal Access Token instead. See [Authentication](https://mcp-atlassian.soomiles.com/docs/authentication).

### 2. Configure Your IDE

Add to your Claude Desktop or Cursor MCP configuration:

```json
{
  "mcpServers": {
    "mcp-atlassian": {
      "command": "uvx",
      "args": ["mcp-atlassian"],
      "env": {
        "JIRA_URL": "https://your-company.atlassian.net",
        "JIRA_USERNAME": "your.email@company.com",
        "JIRA_API_TOKEN": "your_api_token",
        "CONFLUENCE_URL": "https://your-company.atlassian.net/wiki",
        "CONFLUENCE_USERNAME": "your.email@company.com",
        "CONFLUENCE_API_TOKEN": "your_api_token"
      }
    }
  }
}
```

> **Server/Data Center users**: Use `JIRA_PERSONAL_TOKEN` instead of `JIRA_USERNAME` + `JIRA_API_TOKEN`. See [Authentication](https://mcp-atlassian.soomiles.com/docs/authentication) for details.

#### Autohand Code

Use the same `uvx` server with your Atlassian credentials:

```bash
autohand mcp add mcp-atlassian env \
  JIRA_URL=https://your-company.atlassian.net \
  JIRA_USERNAME=your.email@company.com \
  JIRA_API_TOKEN=your_api_token \
  CONFLUENCE_URL=https://your-company.atlassian.net/wiki \
  CONFLUENCE_USERNAME=your.email@company.com \
  CONFLUENCE_API_TOKEN=your_api_token \
  uvx mcp-atlassian
```

Add `--scope project` after `add` to keep the configuration in the current
project. See [Autohand Code](https://github.com/autohandai/code-cli/) for current
installation and CLI details.

### 3. Start Using

Ask your AI assistant to:
- **"Find issues assigned to me in PROJ project"**
- **"Search Confluence for onboarding docs"**
- **"Create a bug ticket for the login issue"**
- **"Update the status of PROJ-123 to Done"**

## SberWorks: Run the Beta on Another Laptop

These instructions use the
[v0.24.0-beta.2 release](https://github.com/akaUNik/mcp-atlassian/releases/tag/v0.24.0-beta.2)
with Jira PAT authentication and verified mTLS. The Docker image supports Linux
amd64 and arm64; no source checkout is required. The commands below are for
macOS/Linux with Docker installed and running. Connect to the corporate network
or VPN required to reach SberWorks.

### 1. Prepare Certificates and Credentials

Create a local directory:

```bash
mkdir -p ~/mcp-sberworks/certs
```

Transfer the certificates through a secure channel and save them as:

- `~/mcp-sberworks/certs/client-combined.pem`: the client certificate and its
  unencrypted private key in one PEM file.
- `~/mcp-sberworks/certs/ca.pem`: the trusted CA bundle in PEM format.

Create `~/mcp-sberworks/.env`, replacing `<YOUR_PAT>` with your Jira PAT:

```dotenv
JIRA_URL=https://sberworks.ru/jira/
JIRA_PERSONAL_TOKEN=<YOUR_PAT>
JIRA_CLIENT_CERT=/certs/client-combined.pem
JIRA_CA_CERT=/certs/ca.pem
JIRA_SSL_VERIFY=true
READ_ONLY_MODE=true
```

If your `.env.pat` contains only the raw token, use that value for
`JIRA_PERSONAL_TOKEN`; Docker's `--env-file` requires `NAME=value` entries.
The certificate paths above refer to files **inside the container**. Keep the
PAT and private key outside Git.

### 2. Start the Server

Restrict access to the credentials and run the container:

```bash
chmod 600 ~/mcp-sberworks/.env ~/mcp-sberworks/certs/client-combined.pem

docker run --rm --name sberworks-jira \
  --user "$(id -u):$(id -g)" \
  --env-file "$HOME/mcp-sberworks/.env" \
  --mount "type=bind,source=$HOME/mcp-sberworks/certs,target=/certs,readonly" \
  -p 127.0.0.1:8000:8000 \
  ghcr.io/akaunik/mcp-atlassian:0.24.0-beta.2 \
  --transport streamable-http --host 0.0.0.0 --port 8000
```

The container runs with your host user ID so it can read the restricted client
PEM. Certificates are mounted read-only, and the published port is accessible
only from the same laptop. Keep this terminal running; press `Ctrl+C` to stop
the server.

### 3. Connect Your MCP Client and Test

In an MCP client that supports **Streamable HTTP**, add this server URL:

```text
http://localhost:8000/mcp
```

Ask the client to find one Jira issue visible to your account. Initial testing
uses `READ_ONLY_MODE=true`, which blocks write tools. Keep
`JIRA_SSL_VERIFY=true` to verify the server certificate.

To check the installed image version separately:

```bash
docker run --rm ghcr.io/akaunik/mcp-atlassian:0.24.0-beta.2 --version
```

The expected Python package version is `0.24.0b2`. See
[configuration](docs/configuration.mdx#sberworks-jira-pat-plus-mtls) and the
[read-only smoke check](docs/troubleshooting.mdx#sberworks-read-only-smoke-check)
for separate certificate/key files, proxy settings, and troubleshooting.

## Documentation

Full documentation is available at **[mcp-atlassian.soomiles.com](https://mcp-atlassian.soomiles.com)**.

Documentation is also available in [llms.txt format](https://llmstxt.org/), which LLMs can consume easily:
- [`llms.txt`](https://mcp-atlassian.soomiles.com/llms.txt) — documentation sitemap
- [`llms-full.txt`](https://mcp-atlassian.soomiles.com/llms-full.txt) — complete documentation

| Topic | Description |
|-------|-------------|
| [Installation](https://mcp-atlassian.soomiles.com/docs/installation) | uvx, Docker, pip, from source |
| [Authentication](https://mcp-atlassian.soomiles.com/docs/authentication) | API tokens, PAT, OAuth 2.0 |
| [Configuration](https://mcp-atlassian.soomiles.com/docs/configuration) | IDE setup, environment variables |
| [HTTP Transport](https://mcp-atlassian.soomiles.com/docs/http-transport) | SSE, streamable-http, multi-user |
| [Tools Reference](https://mcp-atlassian.soomiles.com/docs/tools-reference) | All Jira & Confluence tools |
| [Troubleshooting](https://mcp-atlassian.soomiles.com/docs/troubleshooting) | Common issues & debugging |

## Compatibility

| Product | Deployment | Support |
|---------|------------|---------|
| Confluence | Cloud | Fully supported |
| Confluence | Server/Data Center | Supported (v6.0+) |
| Jira | Cloud | Fully supported |
| Jira | Server/Data Center | Supported (v8.14+) |

## Key Tools

| Jira | Confluence |
|------|------------|
| `jira_search` - Search with JQL | `confluence_search` - Search with CQL |
| `jira_get_issue` - Get issue details | `confluence_get_page` - Get page content |
| `jira_create_issue` - Create issues | `confluence_create_page` - Create pages |
| `jira_update_issue` - Update issues | `confluence_update_page` - Update pages |
| `jira_transition_issue` - Change status | `confluence_add_comment` - Add comments |

**98 tools total** — See [Tools Reference](https://mcp-atlassian.soomiles.com/docs/tools-reference) for the complete list.

## Security

Never share API tokens. Keep `.env` files secure. See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## License

MIT - See [LICENSE](LICENSE). Not an official Atlassian product.
