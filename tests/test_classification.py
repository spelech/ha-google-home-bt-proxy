"""Unit tests for Bluetooth classification and CoD decoding."""

from __future__ import annotations

from custom_components.google_home_bt_proxy.classification import (
    decode_device_class,
    decode_device_type,
    is_resolvable_private_address,
)


def test_decode_device_class_audio_video() -> None:
    """Test decoding CoD values for audio/video devices."""
    # TV: 2884640 (0x2C0420)
    assert "Audio/Video" in decode_device_class(2884640)
    # Set-top box: 2622500 (0x280424)
    assert decode_device_class(2622500) == "Audio/Video (Set-top box)"


def test_decode_device_class_categories() -> None:
    """Test decoding various major categories."""
    # Major 1: Computer
    assert decode_device_class(0x000100) == "Computer"
    # Major 2: Phone
    assert "Phone" in decode_device_class(0x000200)
    # Major 5: Peripheral
    assert decode_device_class(0x000500) == "Peripheral (Input Device)"
    # Major 6: Imaging
    assert decode_device_class(0x000600) == "Imaging (Printer/Scanner)"
    # Major 7: Wearable
    assert decode_device_class(0x000700) == "Wearable (Watch/Tracker)"
    # Major 8: Toy
    assert decode_device_class(0x000800) == "Toy"
    # Major 9: Health
    assert decode_device_class(0x000900) == "Health Device"


def test_decode_device_class_fallback_and_zero() -> None:
    """Test fallback for zero, None, and unknown classes."""
    assert decode_device_class(0) == "BLE Peripheral / Beacon"
    assert decode_device_class(None) == "BLE Peripheral / Beacon"
    assert decode_device_class(0x001F00) == "Uncategorized"
    assert "Device Class" in decode_device_class(0x001500)


def test_decode_device_type() -> None:
    """Test decoding Google device types."""
    assert decode_device_type(1) == "Classic (BR/EDR)"
    assert decode_device_type(2) == "BLE (Bluetooth Low Energy)"
    assert decode_device_type(3) == "Dual-mode (Classic + BLE)"
    assert decode_device_type(None) == "Unknown"
    assert decode_device_type(99) == "Custom (99)"


def test_is_resolvable_private_address() -> None:
    """Test detecting Resolvable Private Addresses (RPAs)."""
    # Leading byte with bits 7-6 set to 01 (0x40-0x7F)
    assert is_resolvable_private_address("41:22:33:1c:cd:13") is True
    assert is_resolvable_private_address("7f:aa:bb:cc:dd:ee") is True
    assert is_resolvable_private_address("50:11:22:33:44:55") is True

    # Leading byte with other bits (e.g. static address 0xC0 or public address 0x00)
    assert is_resolvable_private_address("c0:11:22:33:44:55") is False
    assert is_resolvable_private_address("00:04:4b:b9:b3:f8") is False
    assert is_resolvable_private_address("f8:0f:f9:40:17:a6") is False

    # Invalid input
    assert is_resolvable_private_address("") is False
    assert is_resolvable_private_address("invalid") is False
