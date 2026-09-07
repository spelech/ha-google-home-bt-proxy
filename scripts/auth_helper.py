#!/usr/bin/env python3
"""Standalone Google Home Authentication Helper CLI.

Allows power users and developers to exchange OAuth tokens and verify Google Home
master tokens outside of Home Assistant.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections.abc import Sequence
from typing import Any

import gpsoauth
from glocaltokens.client import GLocalAuthenticationTokens

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger("auth_helper")


INVISIBLE_CHARS_PATTERN = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u2060\u202a-\u202e]")


def clean_string(val: Any) -> str:
    """Strip whitespace, zero-width spaces, and invisible characters."""
    if not val or not isinstance(val, str):
        return ""
    cleaned = INVISIBLE_CHARS_PATTERN.sub("", val)
    return cleaned.strip()


def sanitize_token(token: str) -> str:
    """Extract and sanitize token from raw strings, cookie headers, or devtools copies."""
    if not token or not isinstance(token, str):
        return ""
    token = clean_string(token)
    match_oauth = re.search(r"(oauth2_4/[^\s\"';,]+)", token)
    if match_oauth:
        return match_oauth.group(1)
    match_master = re.search(r"((?:aas_et|oauth2_rt)/[^\s\"';,]+)", token)
    if match_master:
        return match_master.group(1)
    token = re.sub(r"^(?:oauth_token|master_token)\s*[:=]\s*", "", token, flags=re.IGNORECASE)
    token = clean_string(token).strip("\"'").strip(";").strip()
    return token


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for CLI commands."""
    parser = argparse.ArgumentParser(description="Standalone Google Home Authentication Helper CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # exchange command
    parser_exchange = subparsers.add_parser(
        "exchange", help="Exchange a single-use OAuth token for a master token"
    )
    parser_exchange.add_argument("--email", required=True, help="Google account email address")
    parser_exchange.add_argument("--oauth-token", required=True, help="OAuth token (oauth2_4/...)")
    parser_exchange.add_argument(
        "--android-id", default=None, help="Android ID (auto-generated if omitted)"
    )
    parser_exchange.add_argument("--json", action="store_true", help="Output result as raw JSON")

    # verify command
    parser_verify = subparsers.add_parser(
        "verify", help="Validate master token and test retrieval of devices"
    )
    parser_verify.add_argument("--email", required=True, help="Google account email address")
    parser_verify.add_argument("--master-token", required=True, help="Master token (aas_et/...)")
    parser_verify.add_argument(
        "--android-id", default=None, help="Android ID (auto-generated if omitted)"
    )
    parser_verify.add_argument("--json", action="store_true", help="Output result as raw JSON")

    return parser


def handle_exchange(args: argparse.Namespace) -> int:
    """Handle the exchange subcommand."""
    email: str = clean_string(args.email)
    oauth_token: str = sanitize_token(args.oauth_token)
    android_id: str = args.android_id or GLocalAuthenticationTokens._generate_android_id()

    try:
        res = gpsoauth.exchange_token(email, oauth_token, android_id)
    except Exception as err:
        if args.json:
            print(json.dumps({"error": str(err)}, indent=2), file=sys.stderr)
        else:
            print(f"Error exchanging token: {err}", file=sys.stderr)
        return 1

    if not isinstance(res, dict) or "Token" not in res:
        err_msg = (
            res.get("Error", "Failed to exchange token")
            if isinstance(res, dict)
            else "Unknown error"
        )
        if args.json:
            output = (
                {"error": err_msg, "details": res} if isinstance(res, dict) else {"error": err_msg}
            )
            print(json.dumps(output, indent=2), file=sys.stderr)
        else:
            print(f"Error exchanging token: {err_msg}", file=sys.stderr)
        return 1

    master_token = res["Token"]

    if args.json:
        output_data = {
            "master_token": master_token,
            "android_id": android_id,
            **res,
        }
        print(json.dumps(output_data, indent=2))
    else:
        print("Token exchange successful!")
        print(f"master_token: {master_token}")
        print(f"android_id: {android_id}")

    return 0


def handle_verify(args: argparse.Namespace) -> int:
    """Handle the verify subcommand."""
    email: str = clean_string(args.email)
    master_token: str = sanitize_token(args.master_token)
    android_id: str = args.android_id or GLocalAuthenticationTokens._generate_android_id()

    try:
        client = GLocalAuthenticationTokens(
            username=email,
            master_token=master_token,
            android_id=android_id,
        )
        access_token = client.get_access_token()
    except Exception as err:
        if args.json:
            print(json.dumps({"status": "invalid", "error": str(err)}, indent=2), file=sys.stderr)
        else:
            print(f"Error verifying master token: {err}", file=sys.stderr)
        return 1

    if not access_token:
        if args.json:
            print(
                json.dumps(
                    {
                        "status": "invalid",
                        "error": "Invalid master token - could not obtain access token",
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
        else:
            print("Error: Invalid master token - could not obtain access token.", file=sys.stderr)
        return 1

    devices: list[Any] = []
    try:
        raw_devices = client.get_google_devices(disable_discovery=True)
        if isinstance(raw_devices, list):
            devices = raw_devices
        elif hasattr(raw_devices, "__iter__"):
            devices = list(raw_devices)
    except Exception as err:
        _LOGGER.debug("Could not retrieve Homegraph devices: %s", err)

    if args.json:
        dev_list = []
        for dev in devices:
            dev_list.append(
                {
                    "device_id": getattr(dev, "device_id", None),
                    "device_name": getattr(dev, "device_name", str(dev)),
                    "hardware": getattr(dev, "hardware", None),
                }
            )
        print(
            json.dumps(
                {
                    "status": "valid",
                    "email": email,
                    "android_id": android_id,
                    "devices": dev_list,
                },
                indent=2,
            )
        )
    else:
        print("Status: Valid")
        print(f"Email: {email}")
        print(f"Android ID: {android_id}")
        if devices:
            print(f"Discovered {len(devices)} device(s):")
            for dev in devices:
                dev_name = getattr(dev, "device_name", str(dev))
                dev_id = getattr(dev, "device_id", "unknown")
                hardware = getattr(dev, "hardware", "unknown")
                print(f"  - {dev_name} (ID: {dev_id}, Model: {hardware})")
        else:
            print("Discovered devices: None (or Homegraph empty)")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Main entrypoint for auth_helper CLI."""
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    if not args.command:
        parser.print_help()
        return 2

    if args.command == "exchange":
        return handle_exchange(args)
    if args.command == "verify":
        return handle_verify(args)

    return 2


if __name__ == "__main__":
    sys.exit(main())
