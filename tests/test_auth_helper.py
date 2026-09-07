"""Tests for standalone auth_helper CLI utility."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from scripts.auth_helper import main


def test_missing_arguments():
    """Verify that calling CLI without arguments or with missing required flags returns non-zero."""
    # No subcommand provided
    assert main([]) != 0

    # Unknown subcommand
    assert main(["foobar"]) != 0

    # exchange missing --email and --oauth-token
    assert main(["exchange"]) != 0

    # exchange missing --oauth-token
    assert main(["exchange", "--email", "test@example.com"]) != 0

    # verify missing --email and --master-token
    assert main(["verify"]) != 0

    # verify missing --master-token
    assert main(["verify", "--email", "test@example.com"]) != 0


def test_exchange_success(capsys):
    """Verify exchange command outputs master_token on success."""
    fake_master_token = "aas_et/fake_master_token_12345"
    mock_response = {
        "Token": fake_master_token,
        "Auth": "fake_auth_token",
        "Email": "user@example.com",
    }

    with (
        patch("gpsoauth.exchange_token", return_value=mock_response) as mock_exchange,
        patch(
            "scripts.auth_helper.GLocalAuthenticationTokens._generate_android_id",
            return_value="auto_gen_android_id_123",
        ),
    ):
        code = main(
            [
                "exchange",
                "--email",
                "user@example.com",
                "--oauth-token",
                "oauth2_4/dummy_token",
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        assert fake_master_token in captured.out
        assert "auto_gen_android_id_123" in captured.out

        mock_exchange.assert_called_once_with(
            "user@example.com", "oauth2_4/dummy_token", "auto_gen_android_id_123"
        )


def test_exchange_success_custom_android_id(capsys):
    """Verify exchange command uses provided android_id when supplied."""
    fake_master_token = "aas_et/custom_master_token"
    mock_response = {"Token": fake_master_token}

    with patch("gpsoauth.exchange_token", return_value=mock_response) as mock_exchange:
        code = main(
            [
                "exchange",
                "--email",
                "user@example.com",
                "--oauth-token",
                "oauth2_4/dummy_token",
                "--android-id",
                "custom_id_999",
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        assert fake_master_token in captured.out
        assert "custom_id_999" in captured.out

        mock_exchange.assert_called_once_with(
            "user@example.com", "oauth2_4/dummy_token", "custom_id_999"
        )


def test_exchange_success_json_output(capsys):
    """Verify exchange command outputs valid JSON when --json flag is passed."""
    fake_master_token = "aas_et/json_master_token"
    mock_response = {"Token": fake_master_token, "Extra": "data"}

    with patch("gpsoauth.exchange_token", return_value=mock_response):
        code = main(
            [
                "exchange",
                "--email",
                "user@example.com",
                "--oauth-token",
                "oauth2_4/dummy_token",
                "--android-id",
                "custom_id_111",
                "--json",
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["master_token"] == fake_master_token
        assert data["android_id"] == "custom_id_111"
        assert data["Token"] == fake_master_token


def test_exchange_failure_bad_authentication(capsys):
    """Verify exchange command returns non-zero code on BadAuthentication."""
    mock_response = {"Error": "BadAuthentication"}

    with patch("gpsoauth.exchange_token", return_value=mock_response):
        code = main(
            [
                "exchange",
                "--email",
                "user@example.com",
                "--oauth-token",
                "invalid_oauth_token",
            ]
        )

        assert code != 0
        captured = capsys.readouterr()
        assert "BadAuthentication" in (captured.err + captured.out)


def test_exchange_failure_bad_authentication_json(capsys):
    """Verify exchange failure outputs JSON when --json flag is passed."""
    mock_response = {"Error": "BadAuthentication"}

    with patch("gpsoauth.exchange_token", return_value=mock_response):
        code = main(
            [
                "exchange",
                "--email",
                "user@example.com",
                "--oauth-token",
                "invalid_oauth_token",
                "--json",
            ]
        )

        assert code != 0
        captured = capsys.readouterr()
        err_output = captured.err if captured.err else captured.out
        data = json.loads(err_output)
        assert data.get("error") == "BadAuthentication"


def test_exchange_failure_exception(capsys):
    """Verify exchange command handles network or server exceptions cleanly."""
    with patch("gpsoauth.exchange_token", side_effect=RuntimeError("Network failure")):
        code = main(
            [
                "exchange",
                "--email",
                "user@example.com",
                "--oauth-token",
                "oauth2_4/dummy_token",
            ]
        )

        assert code != 0
        captured = capsys.readouterr()
        assert "Network failure" in captured.err


def test_verify_success_with_devices(capsys):
    """Verify verify command succeeds and prints discovered devices."""
    mock_device = MagicMock()
    mock_device.device_name = "Living Room Speaker"
    mock_device.device_id = "device_id_12345"
    mock_device.hardware = "Google Home"

    with patch("scripts.auth_helper.GLocalAuthenticationTokens") as mock_auth_cls:
        mock_client = mock_auth_cls.return_value
        mock_client.get_access_token.return_value = "valid_access_token_123"
        mock_client.get_google_devices.return_value = [mock_device]

        code = main(
            [
                "verify",
                "--email",
                "user@example.com",
                "--master-token",
                "aas_et/valid_master_token",
                "--android-id",
                "android_id_555",
            ]
        )

        assert code == 0
        mock_auth_cls.assert_called_once_with(
            username="user@example.com",
            master_token="aas_et/valid_master_token",
            android_id="android_id_555",
        )
        mock_client.get_access_token.assert_called_once()

        captured = capsys.readouterr()
        assert "Living Room Speaker" in captured.out
        assert "device_id_12345" in captured.out


def test_verify_success_json_output(capsys):
    """Verify verify command outputs valid JSON when --json flag is passed."""
    mock_device = MagicMock()
    mock_device.device_name = "Kitchen Display"
    mock_device.device_id = "device_id_67890"
    mock_device.hardware = "Nest Hub"

    with patch("scripts.auth_helper.GLocalAuthenticationTokens") as mock_auth_cls:
        mock_client = mock_auth_cls.return_value
        mock_client.get_access_token.return_value = "valid_access_token_123"
        mock_client.get_google_devices.return_value = [mock_device]

        code = main(
            [
                "verify",
                "--email",
                "user@example.com",
                "--master-token",
                "aas_et/valid_master_token",
                "--android-id",
                "android_id_555",
                "--json",
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "valid"
        assert data["email"] == "user@example.com"
        assert len(data["devices"]) == 1
        assert data["devices"][0]["device_name"] == "Kitchen Display"


def test_verify_failure_invalid_token(capsys):
    """Verify verify command returns non-zero when access token retrieval fails."""
    with patch("scripts.auth_helper.GLocalAuthenticationTokens") as mock_auth_cls:
        mock_client = mock_auth_cls.return_value
        mock_client.get_access_token.return_value = None

        code = main(
            [
                "verify",
                "--email",
                "user@example.com",
                "--master-token",
                "aas_et/invalid_master_token",
            ]
        )

        assert code != 0
        captured = capsys.readouterr()
        assert "Invalid" in (captured.err + captured.out)


def test_verify_failure_exception(capsys):
    """Verify verify command handles exceptions gracefully and returns non-zero."""
    with patch("scripts.auth_helper.GLocalAuthenticationTokens") as mock_auth_cls:
        mock_client = mock_auth_cls.return_value
        mock_client.get_access_token.side_effect = RuntimeError("Auth failed")

        code = main(
            [
                "verify",
                "--email",
                "user@example.com",
                "--master-token",
                "aas_et/invalid_master_token",
            ]
        )

        assert code != 0
        captured = capsys.readouterr()
        assert "Auth failed" in (captured.err + captured.out)


def test_auth_helper_clean_string_and_sanitize_token():
    """Verify clean_string and sanitize_token handle devtools cookies and invisible chars."""
    from scripts.auth_helper import clean_string, sanitize_token

    # Invisible characters
    assert clean_string(" \u200buser@gmail.com\ufeff ") == "user@gmail.com"
    assert clean_string(None) == ""

    # Cookie and devtools formats
    raw_cookie = 'oauth_token:"oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc..."'
    assert sanitize_token(raw_cookie) == "oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc..."

    cookie_header = "oauth_token=oauth2_4/abc123xyz; Path=/; Domain=.google.com"
    assert sanitize_token(cookie_header) == "oauth2_4/abc123xyz"

    master_cookie = 'master_token: "aas_et/master_abc_123"'
    assert sanitize_token(master_cookie) == "aas_et/master_abc_123"
