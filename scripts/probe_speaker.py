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
    port: int,
    token: str,
    scan_timeout: int = 5,
) -> dict[str, Any]:
    """Probe all Google Home setup endpoints."""
    headers = {
        "cast-local-authorization-token": token,
        "content-type": "application/json",
    }
    base_url = f"https://{host}:{port}" if port == 8443 else f"http://{host}:{port}"
    results: dict[str, Any] = {}

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
            results["scan"] = await resp.json() if resp.status == 200 else {"status": resp.status}
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

    return results


async def main() -> None:
    parser = argparse.ArgumentParser(description="Probe Google Home Bluetooth Endpoints")
    parser.add_argument("--host", required=True, help="Speaker IP address")
    parser.add_argument("--port", type=int, default=8443, help="Port (default: 8443)")
    parser.add_argument("--token", required=True, help="cast-local-authorization-token")
    parser.add_argument("--timeout", type=int, default=5, help="Scan timeout in seconds")
    args = parser.parse_args()

    async with aiohttp.ClientSession() as session:
        output = await probe_endpoints(session, args.host, args.port, args.token, args.timeout)
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
