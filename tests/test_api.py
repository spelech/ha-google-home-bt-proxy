"""Tests for GoogleHomeApiClient."""

from __future__ import annotations

import aiohttp
import pytest
from aiohttp import web

from custom_components.google_home_bt_proxy.api import (
    GoogleHomeApiClient,
    SpeakerConnectionError,
    TokenExpiredError,
)
from custom_components.google_home_bt_proxy.models import SpeakerNode


@pytest.mark.asyncio
async def test_start_scan_and_get_results(aiohttp_client) -> None:
    """Verify start_scan and get_scan_results flow successfully."""
    scan_triggered = False

    async def handle_scan(request: web.Request) -> web.Response:
        nonlocal scan_triggered
        assert request.headers.get("cast-local-authorization-token") == "test-token"
        payload = await request.json()
        assert payload.get("enable") is True
        scan_triggered = True
        return web.json_response({"success": True})

    async def handle_results(request: web.Request) -> web.Response:
        assert request.headers.get("cast-local-authorization-token") == "test-token"
        return web.json_response(
            [
                {
                    "mac_address": "11:22:33:44:55:66",
                    "rssi": -68,
                    "name": "SmartBand",
                    "device_type": 1,
                },
                {
                    "mac_address": "AA:BB:CC:DD:EE:FF",
                    "rssi": -85,
                    "name": "Beacon2",
                    "device_type": 2,
                },
                {"mac_address": None, "rssi": -50},  # Missing mac
                {"mac_address": "12:34:56:78:90:AB", "rssi": None},  # Missing rssi
                "invalid_non_dict_element",  # Non-dict item
            ]
        )

    app = web.Application()
    app.router.add_post("/setup/bluetooth/scan", handle_scan)
    app.router.add_get("/setup/bluetooth/scan_results", handle_results)

    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    success = await api_client.start_scan(speaker, timeout=5)
    assert success is True
    assert scan_triggered is True
    assert speaker.available is True

    devices = await api_client.get_scan_results(speaker)
    assert len(devices) == 2
    assert devices[0].mac_address == "11:22:33:44:55:66"
    assert devices[0].rssi == -68
    assert devices[0].name == "SmartBand"
    assert devices[1].mac_address == "AA:BB:CC:DD:EE:FF"
    assert devices[1].rssi == -85


@pytest.mark.asyncio
async def test_get_scan_results_malformed_json(aiohttp_client) -> None:
    """Verify get_scan_results handles non-list JSON gracefully."""

    async def handle_malformed(request: web.Request) -> web.Response:
        return web.json_response({"error": "scanner_busy", "code": 503})

    app = web.Application()
    app.router.add_get("/setup/bluetooth/scan_results", handle_malformed)

    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    results = await api_client.get_scan_results(speaker)
    assert results == []
    assert speaker.available is True


@pytest.mark.asyncio
async def test_start_scan_non_200(aiohttp_client) -> None:
    """Verify start_scan handles non-200 HTTP status properly."""

    async def handle_scan(request: web.Request) -> web.Response:
        return web.Response(status=500)

    app = web.Application()
    app.router.add_post("/setup/bluetooth/scan", handle_scan)

    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    success = await api_client.start_scan(speaker, timeout=5)
    assert success is False


@pytest.mark.asyncio
async def test_get_scan_results_non_200(aiohttp_client) -> None:
    """Verify get_scan_results returns empty list on non-200."""

    async def handle_results(request: web.Request) -> web.Response:
        return web.Response(status=500)

    app = web.Application()
    app.router.add_get("/setup/bluetooth/scan_results", handle_results)

    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    results = await api_client.get_scan_results(speaker)
    assert results == []


@pytest.mark.asyncio
async def test_token_expired_error(aiohttp_client) -> None:
    """Verify TokenExpiredError is raised on 401."""

    async def handle_unauthorized(request: web.Request) -> web.Response:
        return web.Response(status=401)

    app = web.Application()
    app.router.add_post("/setup/bluetooth/scan", handle_unauthorized)
    app.router.add_get("/setup/bluetooth/scan_results", handle_unauthorized)
    app.router.add_get("/setup/eureka_info", handle_unauthorized)

    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="expired-token",
    )

    with pytest.raises(TokenExpiredError):
        await api_client.start_scan(speaker)

    with pytest.raises(TokenExpiredError):
        await api_client.get_scan_results(speaker)

    with pytest.raises(TokenExpiredError):
        await api_client.get_device_info(speaker)


@pytest.mark.asyncio
async def test_get_device_info_success_and_non_200(aiohttp_client) -> None:
    """Verify get_device_info retrieves eureka_info correctly."""
    eureka_called = False

    async def handle_eureka(request: web.Request) -> web.Response:
        nonlocal eureka_called
        eureka_called = True
        return web.json_response({"name": "Test Speaker", "build_version": "1.56"})

    app = web.Application()
    app.router.add_get("/setup/eureka_info", handle_eureka)

    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    info = await api_client.get_device_info(speaker)
    assert eureka_called is True
    assert info.get("name") == "Test Speaker"


@pytest.mark.asyncio
async def test_get_device_info_non_200(aiohttp_client) -> None:
    """Verify get_device_info returns empty dict on non-200."""

    async def handle_eureka(request: web.Request) -> web.Response:
        return web.Response(status=500)

    app = web.Application()
    app.router.add_get("/setup/eureka_info", handle_eureka)

    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    info = await api_client.get_device_info(speaker)
    assert info == {}


@pytest.mark.asyncio
async def test_connection_error_raises_speaker_connection_error() -> None:
    """Verify SpeakerConnectionError is raised on connection failure."""
    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address="127.0.0.1",
        auth_token="test-token",
        available=True,
    )

    # Use an invalid port to force connection failure
    async with aiohttp.ClientSession() as session:
        api_client = GoogleHomeApiClient(session, port=1, use_ssl=False, request_timeout=1)

        with pytest.raises(SpeakerConnectionError):
            await api_client.start_scan(speaker)
        assert speaker.available is False

        with pytest.raises(SpeakerConnectionError):
            await api_client.get_scan_results(speaker)
        assert speaker.available is False

        with pytest.raises(SpeakerConnectionError):
            await api_client.get_device_info(speaker)
        assert speaker.available is False


@pytest.mark.asyncio
async def test_get_bluetooth_status(aiohttp_client) -> None:
    """Verify get_bluetooth_status returns bluetooth status data."""

    async def handle_status(request: web.Request) -> web.Response:
        assert request.headers.get("cast-local-authorization-token") == "test-token"
        return web.json_response(
            {
                "connected_devices": [
                    {"mac_address": "11:22:33:44:55:66", "name": "Phone", "device_class": 5898764}
                ]
            }
        )

    app = web.Application()
    app.router.add_get("/setup/bluetooth/status", handle_status)
    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    status = await api_client.get_bluetooth_status(speaker)
    assert "connected_devices" in status
    assert len(status["connected_devices"]) == 1
    assert status["connected_devices"][0]["name"] == "Phone"
