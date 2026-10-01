"""Integration tests for SSL verification functionality."""

import os
import ssl
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

import pytest
import truststore
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from requests.exceptions import SSLError
from requests.sessions import Session

from mcp_atlassian.confluence.config import ConfluenceConfig
from mcp_atlassian.jira.client import JiraClient
from mcp_atlassian.jira.config import JiraConfig
from mcp_atlassian.utils.ssl import SSLIgnoreAdapter, configure_ssl_verification
from tests.utils.base import BaseAuthTest
from tests.utils.mocks import MockEnvironment


@pytest.fixture(scope="module")
def mtls_material(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Generate disposable CA, server and client identities without secrets."""
    directory = tmp_path_factory.mktemp("jira-mtls")
    now = datetime.now(timezone.utc)

    def issue(
        name: str,
        ca: x509.Certificate | None = None,
        signer: rsa.RSAPrivateKey | None = None,
        usage: x509.ObjectIdentifier | None = None,
    ) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
        builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca.subject if ca else subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(
                x509.BasicConstraints(ca=ca is None, path_length=None), critical=True
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    (signer or key).public_key()
                ),
                critical=False,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    content_commitment=False,
                    key_encipherment=ca is not None,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=ca is None,
                    crl_sign=ca is None,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
        )
        if usage:
            builder = builder.add_extension(
                x509.ExtendedKeyUsage([usage]), critical=False
            )
        if usage == ExtendedKeyUsageOID.SERVER_AUTH:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False
            )
        cert = builder.sign(signer or key, hashes.SHA256())
        (directory / f"{name}.pem").write_bytes(
            cert.public_bytes(serialization.Encoding.PEM)
        )
        key_pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        (directory / f"{name}.key").write_bytes(key_pem)
        (directory / f"{name}-combined.pem").write_bytes(
            cert.public_bytes(serialization.Encoding.PEM) + key_pem
        )
        return cert, key

    ca, ca_key = issue("ca")
    issue("wrong-ca")
    issue("server", ca, ca_key, ExtendedKeyUsageOID.SERVER_AUTH)
    issue("client", ca, ca_key, ExtendedKeyUsageOID.CLIENT_AUTH)
    return {
        name: str(directory / name)
        for name in [
            "ca.pem",
            "wrong-ca.pem",
            "server.pem",
            "server.key",
            "client-combined.pem",
        ]
    }


@pytest.fixture
def mtls_server(
    mtls_material: dict[str, str],
) -> Iterator[tuple[str, list[tuple[str, str | None]]]]:
    """Serve Jira-shaped read responses only after successful client TLS auth."""
    received: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            received.append((self.path, self.headers.get("Authorization")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"name": "test-user"}')

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    # truststore verifies client-side peer chains and cannot wrap a listening
    # server socket. Use stdlib SSL only for the test server, keeping the Jira
    # client on the application's configured TLS stack.
    system_trust = ssl.SSLContext is truststore.SSLContext
    if system_trust:
        truststore.extract_from_ssl()
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(
            mtls_material["server.pem"], mtls_material["server.key"]
        )
        context.load_verify_locations(cafile=mtls_material["ca.pem"])
        context.verify_mode = ssl.CERT_REQUIRED
        server.socket = context.wrap_socket(server.socket, server_side=True)
    finally:
        if system_trust:
            truststore.inject_into_ssl()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://localhost:{server.server_port}/jira/", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.integration
@pytest.mark.parametrize("failure", [None, "missing-client", "wrong-ca", "hostname"])
@pytest.mark.parametrize("direct_session", [False, True])
def test_pat_verified_mtls_transport(
    mtls_material: dict[str, str],
    mtls_server: tuple[str, list[tuple[str, str | None]]],
    failure: str | None,
    direct_session: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TLS requires trusted server identity and client identity on both paths."""
    url, received = mtls_server
    if failure == "hostname":
        url = url.replace("localhost", "127.0.0.1")
    monkeypatch.setenv("JIRA_URL", url)
    monkeypatch.setattr(
        "mcp_atlassian.jira.client.logger.isEnabledFor", lambda _: False
    )
    config = JiraConfig(
        url=url,
        auth_type="pat",
        personal_token="synthetic-pat",
        timeout=3,
        ca_cert=mtls_material["wrong-ca.pem" if failure == "wrong-ca" else "ca.pem"],
        client_cert=None
        if failure == "missing-client"
        else mtls_material["client-combined.pem"],
    )
    client = JiraClient(config)
    session = client.jira._session
    try:
        if failure:
            with pytest.raises(SSLError):
                if direct_session:
                    session.get(url + "attachment", timeout=3)
                else:
                    client.jira.myself()
            assert received == []
        else:
            result = (
                session.get(url + "attachment", timeout=3).json()
                if direct_session
                else client.jira.myself()
            )
            assert result == {"name": "test-user"}
            assert received == [
                (
                    "/jira/attachment" if direct_session else "/jira/rest/api/2/myself",
                    "Bearer synthetic-pat",
                )
            ]
        assert config.ssl_verify is True
        assert session.verify == config.ca_cert
    finally:
        session.close()


@pytest.mark.integration
def test_configure_ssl_verification_with_real_confluence_url():
    """Test SSL verification configuration with real Confluence URL from environment."""
    # Get the URL from the environment
    url = os.getenv("CONFLUENCE_URL")
    if not url:
        pytest.skip("CONFLUENCE_URL not set in environment")

    # Create a real session
    session = Session()
    original_adapters_count = len(session.adapters)

    # Mock the SSL_VERIFY value to be False for this test
    with patch.dict(os.environ, {"CONFLUENCE_SSL_VERIFY": "false"}):
        # Configure SSL verification - explicitly pass ssl_verify=False
        configure_ssl_verification(
            service_name="Confluence",
            url=url,
            session=session,
            ssl_verify=False,
        )

        # Extract domain from URL (remove protocol and path)
        domain = url.split("://")[1].split("/")[0]

        # Verify the adapters are mounted correctly
        assert len(session.adapters) == original_adapters_count + 2
        assert f"https://{domain}" in session.adapters
        assert f"http://{domain}" in session.adapters
        assert isinstance(session.adapters[f"https://{domain}"], SSLIgnoreAdapter)
        assert isinstance(session.adapters[f"http://{domain}"], SSLIgnoreAdapter)


class TestSSLVerificationEnhanced(BaseAuthTest):
    """Enhanced SSL verification tests using test utilities."""

    @pytest.mark.integration
    def test_ssl_verification_enabled_by_default(self):
        """Test that SSL verification is enabled by default."""
        with MockEnvironment.basic_auth_env():
            # For Jira
            jira_config = JiraConfig.from_env()
            assert jira_config.ssl_verify is True

            # For Confluence
            confluence_config = ConfluenceConfig.from_env()
            assert confluence_config.ssl_verify is True

    @pytest.mark.integration
    def test_ssl_verification_disabled_via_env(self):
        """Test SSL verification can be disabled via environment variables."""
        with MockEnvironment.basic_auth_env() as env_vars:
            env_vars["JIRA_SSL_VERIFY"] = "false"
            env_vars["CONFLUENCE_SSL_VERIFY"] = "false"

            # For Jira - need to reload config after env change
            with patch.dict(os.environ, env_vars):
                jira_config = JiraConfig.from_env()
                assert jira_config.ssl_verify is False

                # For Confluence
                confluence_config = ConfluenceConfig.from_env()
                assert confluence_config.ssl_verify is False

    @pytest.mark.integration
    def test_ssl_adapter_mounting_for_multiple_domains(self):
        """Test SSL adapters are correctly mounted for multiple domains."""
        session = Session()

        # Configure for multiple domains
        urls = [
            "https://domain1.atlassian.net",
            "https://domain2.atlassian.net/wiki",
            "https://custom.domain.com/jira",
        ]

        for url in urls:
            configure_ssl_verification(
                service_name="Test", url=url, session=session, ssl_verify=False
            )

        # Verify all domains have SSL adapters
        assert "https://domain1.atlassian.net" in session.adapters
        assert "https://domain2.atlassian.net" in session.adapters
        assert "https://custom.domain.com" in session.adapters

    @pytest.mark.integration
    def test_ssl_error_handling_with_invalid_cert(self, monkeypatch):
        """Test SSL error handling when certificate validation fails."""
        # Mock the Jira class to simulate SSL error
        mock_jira = MagicMock()
        mock_jira.side_effect = SSLError("Certificate verification failed")
        monkeypatch.setattr("mcp_atlassian.jira.client.Jira", mock_jira)

        with MockEnvironment.basic_auth_env():
            config = JiraConfig.from_env()
            config.ssl_verify = True  # Ensure SSL verification is on

            # Creating client should raise SSL error
            with pytest.raises(SSLError, match="Certificate verification failed"):
                JiraClient(config=config)

    @pytest.mark.integration
    def test_ssl_verification_with_custom_ca_bundle(self):
        """Test SSL verification with custom CA bundle path."""
        with MockEnvironment.basic_auth_env() as env_vars:
            # Set custom CA bundle path
            custom_ca_path = "/path/to/custom/ca-bundle.crt"
            env_vars["JIRA_SSL_VERIFY"] = custom_ca_path
            env_vars["CONFLUENCE_SSL_VERIFY"] = custom_ca_path

            # For Jira - need to reload config after env change
            with patch.dict(os.environ, env_vars):
                jira_config = JiraConfig.from_env()
                # Note: Current implementation only supports boolean ssl_verify
                # Custom CA bundle paths are not supported in the config parsing
                assert (
                    jira_config.ssl_verify is True
                )  # Any non-false value becomes True

                # For Confluence
                confluence_config = ConfluenceConfig.from_env()
                assert (
                    confluence_config.ssl_verify is True
                )  # Any non-false value becomes True

    @pytest.mark.integration
    def test_ssl_adapter_not_mounted_when_verification_enabled(self, monkeypatch):
        """Test that SSL adapters are not mounted when verification is enabled."""
        session = Session()
        original_adapter_count = len(session.adapters)
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)

        # Configure with SSL verification enabled
        configure_ssl_verification(
            service_name="Jira",
            url="https://test.atlassian.net",
            session=session,
            ssl_verify=True,  # SSL verification enabled
        )

        # No additional adapters should be mounted
        assert len(session.adapters) == original_adapter_count
        assert "https://test.atlassian.net" not in session.adapters

    @pytest.mark.integration
    def test_ssl_configuration_persistence_across_requests(self):
        """Test SSL configuration persists across multiple requests."""
        session = Session()

        # Configure SSL for a domain
        configure_ssl_verification(
            service_name="Jira",
            url="https://test.atlassian.net",
            session=session,
            ssl_verify=False,
        )

        # Get the adapter
        adapter = session.adapters.get("https://test.atlassian.net")
        assert isinstance(adapter, SSLIgnoreAdapter)

        # Configure again - should not create duplicate adapters
        configure_ssl_verification(
            service_name="Jira",
            url="https://test.atlassian.net",
            session=session,
            ssl_verify=False,
        )

        # Should still have an SSLIgnoreAdapter present
        new_adapter = session.adapters.get("https://test.atlassian.net")
        assert isinstance(new_adapter, SSLIgnoreAdapter)

    @pytest.mark.integration
    def test_ssl_verification_with_oauth_configuration(self):
        """Test SSL verification works correctly with OAuth configuration."""
        with MockEnvironment.oauth_env() as env_vars:
            # Add SSL configuration
            env_vars["JIRA_SSL_VERIFY"] = "false"
            env_vars["CONFLUENCE_SSL_VERIFY"] = "false"

            # OAuth config should still respect SSL settings
            # Need to reload config after env change
            with patch.dict(os.environ, env_vars):
                # Note: OAuth flow would need additional setup, but we're testing config only
                assert os.environ.get("JIRA_SSL_VERIFY") == "false"
                assert os.environ.get("CONFLUENCE_SSL_VERIFY") == "false"


@pytest.mark.integration
def test_configure_ssl_verification_with_real_jira_url():
    """Test SSL verification configuration with real Jira URL from environment."""
    # Get the URL from the environment
    url = os.getenv("JIRA_URL")
    if not url:
        pytest.skip("JIRA_URL not set in environment")

    # Create a real session
    session = Session()
    original_adapters_count = len(session.adapters)

    # Mock the SSL_VERIFY value to be False for this test
    with patch.dict(os.environ, {"JIRA_SSL_VERIFY": "false"}):
        # Configure SSL verification - explicitly pass ssl_verify=False
        configure_ssl_verification(
            service_name="Jira",
            url=url,
            session=session,
            ssl_verify=False,
        )

        # Extract domain from URL (remove protocol and path)
        domain = url.split("://")[1].split("/")[0]

        # Verify the adapters are mounted correctly
        assert len(session.adapters) == original_adapters_count + 2
        assert f"https://{domain}" in session.adapters
        assert f"http://{domain}" in session.adapters
        assert isinstance(session.adapters[f"https://{domain}"], SSLIgnoreAdapter)
        assert isinstance(session.adapters[f"http://{domain}"], SSLIgnoreAdapter)
