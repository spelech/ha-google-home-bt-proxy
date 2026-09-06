#!/usr/bin/env python3
"""Empirical hardware probe script for Google Home Bluetooth endpoints."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from typing import Any

import aiohttp

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger("probe_speaker")


async def probe_endpoints(
    session: aiohttp.ClientSession,
    host: str,
    port: int = 8443,
    token: str | None = None,
    scan_timeout: int = 5,
    check_cast: bool = False,
) -> dict[str, Any]:
    """Probe all Google Home setup endpoints."""
    headers: dict[str, str] = {
        "content-type": "application/json",
    }
    if token:
        headers["cast-local-authorization-token"] = token

    base_url = f"https://{host}:{port}" if port == 8443 else f"http://{host}:{port}"
    results: dict[str, Any] = {}

    # Optional Cast V2 TCP probe (Port 8009)
    if check_cast:
        results["cast_v2"] = await _check_cast_v2(host)

    # 1. Eureka Info
    try:
        async with session.get(f"{base_url}/setup/eureka_info", headers=headers, ssl=False) as resp:
            results["eureka"] = await resp.json() if resp.status == 200 else {"status": resp.status}
    except Exception as err:
        results["eureka"] = {"error": str(err)}

    # 2. Bluetooth Status
    try:
        async with session.get(
            f"{base_url}/setup/bluetooth/status", headers=headers, ssl=False
        ) as resp:
            results["status"] = await resp.json() if resp.status == 200 else {"status": resp.status}
    except Exception as err:
        results["status"] = {"error": str(err)}

    # 3. Trigger Scan
    scan_payload = {"enable": True, "clear_results": True, "timeout": scan_timeout}
    try:
        async with session.post(
            f"{base_url}/setup/bluetooth/scan",
            headers=headers,
            json=scan_payload,
            ssl=False,
        ) as resp:
            if resp.status == 200:
                try:
                    results["scan"] = await resp.json()
                except Exception:
                    results["scan"] = {"status": 200, "message": "Scan started successfully"}
            else:
                results["scan"] = {"status": resp.status}
    except Exception as err:
        results["scan"] = {"error": str(err)}

    # Wait for hardware scan duration
    if scan_timeout > 0:
        await asyncio.sleep(scan_timeout)

    # 4. Scan Results
    try:
        async with session.get(
            f"{base_url}/setup/bluetooth/scan_results", headers=headers, ssl=False
        ) as resp:
            results["results"] = (
                await resp.json() if resp.status == 200 else {"status": resp.status}
            )
    except Exception as err:
        results["results"] = {"error": str(err)}

    results["classification"] = classify_probe_result(results)
    return results


async def _check_cast_v2(
    host: str, port: int = 8009, connect_timeout: float = 2.0
) -> dict[str, Any]:
    """Test raw TCP socket connection to Cast V2 port 8009."""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=connect_timeout
        )
        writer.close()
        await writer.wait_closed()
        return {"open": True, "port": port}
    except Exception as err:
        return {"open": False, "port": port, "error": str(err)}


def classify_probe_result(results: dict[str, Any]) -> str:
    """Classify device compatibility based on endpoint responses."""
    status_res = results.get("status", {})
    scan_res = results.get("scan", {})

    status_code = status_res.get("status") if isinstance(status_res, dict) else None
    scan_code = scan_res.get("status") if isinstance(scan_res, dict) else None

    if status_code == 404:
        return (
            "Android TV / Google TV: Cast V2 supported, local BLE scanning endpoint "
            "not implemented (HTTP 404)."
        )
    if scan_code == 400:
        return (
            "Third-Party Cast Device: Cast V2 supported, active BLE scanning rejected (HTTP 400)."
        )
    if status_code == 401 or (isinstance(status_res, dict) and "scanning_enabled" in status_res):
        return "Google Home / Nest Speaker: Fully compatible hardware for BLE proxy scanning."
    return f"Unknown / Partially supported: status={status_code}, scan={scan_code}"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Google Home Bluetooth Endpoints")
    parser.add_argument("--host", required=True, help="Speaker IP address")
    parser.add_argument("--port", type=int, default=8443, help="Port (default: 8443)")
    parser.add_argument(
        "--token", default=None, help="cast-local-authorization-token (optional for open endpoints)"
    )
    parser.add_argument("--timeout", type=int, default=5, help="Scan timeout in seconds")
    parser.add_argument("--check-cast", action="store_true", help="Probe Cast V2 port 8009")
    args = parser.parse_args()

    async with aiohttp.ClientSession() as session:
        output = await probe_endpoints(
            session, args.host, args.port, args.token, args.timeout, args.check_cast
        )
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
