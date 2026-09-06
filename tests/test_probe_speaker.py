from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web

from scripts.probe_speaker import _check_cast_v2, probe_endpoints


@pytest.mark.asyncio
async def test_probe_endpoints_success(aiohttp_client):
    """Verify probe_endpoints queries all target endpoints."""

    async def handle_eureka(request):
        return web.json_response({"name": "Living Room Speaker", "build_version": "1.56"})

    async def handle_status(request):
        return web.json_response({"scanning_enabled": True})

    async def handle_scan(request):
        data = await request.json()
        assert data.get("enable") is True
        return web.json_response({"success": True})

    async def handle_results(request):
        return web.json_response(
            [{"mac_address": "AA:BB:CC:DD:EE:FF", "rssi": -65, "name": "Beacon1"}]
        )

    app = web.Application()
    app.router.add_get("/setup/eureka_info", handle_eureka)
    app.router.add_get("/setup/bluetooth/status", handle_status)
    app.router.add_post("/setup/bluetooth/scan", handle_scan)
    app.router.add_get("/setup/bluetooth/scan_results", handle_results)

    client = await aiohttp_client(app)
    results = await probe_endpoints(
        client.session, str(client.server.host), client.server.port, "dummy-token"
    )

    assert results["eureka"]["name"] == "Living Room Speaker"
    assert results["status"]["scanning_enabled"] is True
    assert results["scan"]["success"] is True
    assert len(results["results"]) == 1
    assert results["results"][0]["mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert "Google Home / Nest Speaker" in results["classification"]


@pytest.mark.asyncio
async def test_probe_endpoints_android_tv_404(aiohttp_client):
    """Verify probe_endpoints classifies 404 status as Android TV."""

    async def handle_empty(request):
        return web.json_response({})

    async def handle_404(request):
        return web.Response(status=404)

    app = web.Application()
    app.router.add_get("/setup/eureka_info", handle_empty)
    app.router.add_get("/setup/bluetooth/status", handle_404)
    app.router.add_post("/setup/bluetooth/scan", handle_404)
    app.router.add_get("/setup/bluetooth/scan_results", handle_404)

    client = await aiohttp_client(app)
    results = await probe_endpoints(
        client.session, str(client.server.host), client.server.port, token=None, scan_timeout=0
    )
    assert "Android TV" in results["classification"]


@pytest.mark.asyncio
async def test_probe_endpoints_third_party_400(aiohttp_client):
    """Verify probe_endpoints classifies 400 scan rejection as third party device."""

    async def handle_empty(request):
        return web.json_response({})

    async def handle_scan(request):
        return web.Response(status=400)

    async def handle_empty_list(request):
        return web.json_response([])

    app = web.Application()
    app.router.add_get("/setup/eureka_info", handle_empty)
    app.router.add_get("/setup/bluetooth/status", handle_empty)
    app.router.add_post("/setup/bluetooth/scan", handle_scan)
    app.router.add_get("/setup/bluetooth/scan_results", handle_empty_list)

    client = await aiohttp_client(app)
    results = await probe_endpoints(
        client.session, str(client.server.host), client.server.port, token=None, scan_timeout=0
    )
    assert "Third-Party Cast Device" in results["classification"]


@pytest.mark.asyncio
async def test_probe_cast_v2(monkeypatch):
    """Verify _check_cast_v2 socket probe handles open and closed ports."""
    # Test open socket
    mock_writer = MagicMock()
    mock_writer.wait_closed = AsyncMock()
    monkeypatch.setattr(
        "asyncio.open_connection", AsyncMock(return_value=(AsyncMock(), mock_writer))
    )
    res = await _check_cast_v2("127.0.0.1", 8009)
    assert res["open"] is True

    # Test connection refused
    monkeypatch.setattr(
        "asyncio.open_connection",
        AsyncMock(side_effect=ConnectionRefusedError("Connection refused")),
    )
    res_err = await _check_cast_v2("127.0.0.1", 8009)
    assert res_err["open"] is False
    assert "Connection refused" in res_err["error"]
