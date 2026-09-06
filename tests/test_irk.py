"""Unit tests for in-integration IRK resolution."""

from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from custom_components.google_home_bt_proxy.irk import IrkResolver, parse_irk_config


def test_parse_irk_config() -> None:
    """Test parsing IRK configuration text."""
    # Empty
    assert parse_irk_config("") == {}

    # Newline-separated
    text = (
        "0123456789abcdef0123456789abcdef : Steve Phone\n"
        "fedcba9876543210fedcba9876543210: Watch\n"
        "invalid_length: Bad\n"
        "no_colon_entry\n"
    )
    parsed = parse_irk_config(text)
    assert len(parsed) == 2
    assert parsed["0123456789abcdef0123456789abcdef"] == "Steve Phone"
    assert parsed["fedcba9876543210fedcba9876543210"] == "Watch"

    # Comma-separated
    comma_text = (
        "0123456789abcdef0123456789abcdef: Steve Phone, fedcba9876543210fedcba9876543210: Watch"
    )
    parsed_comma = parse_irk_config(comma_text)
    assert len(parsed_comma) == 2


def test_irk_resolver_matching() -> None:
    """Test resolving an RPA using a registered IRK key."""
    irk_hex = "0123456789abcdef0123456789abcdef"
    irk_bytes = bytes.fromhex(irk_hex)

    resolver = IrkResolver({irk_hex: "Steve Phone"})
    assert resolver.count == 1

    # Generate a cryptographically valid RPA for this IRK
    prand = bytes([0x41, 0x22, 0x33])  # top 2 bits == 01
    pt = b"\x00" * 13 + prand
    encryptor = Cipher(algorithms.AES(irk_bytes), modes.ECB()).encryptor()
    ct = encryptor.update(pt) + encryptor.finalize()
    rpa_bytes = prand + ct[13:]
    matching_mac = ":".join(f"{b:02x}" for b in rpa_bytes)

    # Must resolve to the friendly name
    assert resolver.resolve(matching_mac) == "Steve Phone"

    # Non-matching RPA (change hash)
    non_matching_mac = "41:22:33:ff:ff:ff"
    assert resolver.resolve(non_matching_mac) is None

    # Non-RPA address (top bits not 01)
    non_rpa_mac = "00:11:22:33:44:55"
    assert resolver.resolve(non_rpa_mac) is None


def test_irk_resolver_invalid_keys() -> None:
    """Test that invalid keys are safely ignored without crashing."""
    resolver = IrkResolver(
        {"too_short": "Bad Key", "invalid_hex_zzzzzzzzzzzzzzzzzzzzzz": "Not Hex"}
    )
    assert resolver.count == 0
    assert resolver.resolve("41:22:33:44:55:66") is None
