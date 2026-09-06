"""Mock Google Home local HTTPS API server for simulation and disturbance testing."""

from __future__ import annotations

from aiohttp import web


class MockGoogleHomeSpeaker:
    """Simulates a Google Home speaker with configurable disturbances."""

    def __init__(self, name: str = "Mock Speaker", auth_token: str = "valid-token") -> None:
        self.name = name
        self.auth_token = auth_token
        self.simulate_401 = False
        self.simulate_drop = False
        self.simulate_500 = False
        self.scan_count = 0
        self.mock_devices: list[dict[str, object]] = [
            {
                "mac_address": f"AA:BB:CC:11:22:{i:02X}",
                "rssi": -60 - (i % 30),
                "name": f"Beacon_{i}",
                "device_type": 1,
            }
            for i in range(25)
        ]

    async def handle_eureka(self, request: web.Request) -> web.Response:
        if self.simulate_drop:
            if request.transport:
                request.transport.abort()
            return web.Response(status=500)
        if self.simulate_500:
            return web.Response(status=500)
        if self._is_unauthorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response({"name": self.name, "build_version": "2.0.0"})

    async def handle_scan(self, request: web.Request) -> web.Response:
        if self.simulate_drop:
            if request.transport:
                request.transport.abort()
            return web.Response(status=500)
        if self.simulate_500:
            return web.Response(status=500)
        if self._is_unauthorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        self.scan_count += 1
        return web.json_response({"success": True})

    async def handle_results(self, request: web.Request) -> web.Response:
        if self.simulate_drop:
            if request.transport:
                request.transport.abort()
            return web.Response(status=500)
        if self.simulate_500:
            return web.Response(status=500)
        if self._is_unauthorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response(self.mock_devices)

    def _is_unauthorized(self, request: web.Request) -> bool:
        token = request.headers.get("cast-local-authorization-token")
        return self.simulate_401 or token != self.auth_token

    def create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/setup/eureka_info", self.handle_eureka)
        app.router.add_post("/setup/bluetooth/scan", self.handle_scan)
        app.router.add_get("/setup/bluetooth/scan_results", self.handle_results)
        return app
