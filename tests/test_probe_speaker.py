"""Tests for probe_speaker script."""

import pytest
from aiohttp import web

from scripts.probe_speaker import probe_endpoints


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
