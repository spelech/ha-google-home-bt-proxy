"""Classification and decoding utilities for Bluetooth devices and CoD."""

from __future__ import annotations

MAJOR_DEVICE_CLASSES: dict[int, str] = {
    0x00: "Miscellaneous",
    0x01: "Computer",
    0x02: "Phone",
    0x03: "Network Access Point",
    0x04: "Audio/Video",
    0x05: "Peripheral",
    0x06: "Imaging",
    0x07: "Wearable",
    0x08: "Toy",
    0x09: "Health",
    0x1F: "Uncategorized",
}

AUDIO_VIDEO_MINOR_CLASSES: dict[int, str] = {
    0: "Uncategorized Audio/Video",
    1: "Wearable Headset",
    2: "Hands-free Device",
    4: "Microphone",
    5: "Loudspeaker",
    6: "Headphones",
    7: "Portable Audio",
    8: "Car Audio",
    9: "Set-top box",
    10: "HiFi Audio Device",
    11: "VCR",
    12: "Video Camera",
    13: "Camcorder",
    14: "Video Monitor",
    15: "TV / Video Display",
    16: "Video Conferencing",
}

PHONE_MINOR_CLASSES: dict[int, str] = {
    1: "Cellular Phone",
    2: "Cordless Phone",
    3: "Smartphone",
    4: "Wired Modem / Voice Gateway",
}

DEVICE_TYPE_NAMES: dict[int, str] = {
    1: "Classic (BR/EDR)",
    2: "BLE (Bluetooth Low Energy)",
    3: "Dual-mode (Classic + BLE)",
}


def decode_device_type(device_type: int | None) -> str:
    """Return human-readable representation of Google device_type."""
    if device_type is None:
        return "Unknown"
    return DEVICE_TYPE_NAMES.get(device_type, f"Custom ({device_type})")


def decode_device_class(cod: int | None) -> str:
    """Decode 24-bit Bluetooth SIG Class of Device into human-readable description."""
    if not cod:
        return "BLE Peripheral / Beacon"

    major = (cod >> 8) & 0x1F
    minor = (cod >> 2) & 0x3F

    if major == 0x04:  # Audio / Video
        sub = AUDIO_VIDEO_MINOR_CLASSES.get(minor, f"A/V Device ({minor})")
        return f"Audio/Video ({sub})"

    if major == 0x02:  # Phone
        sub = PHONE_MINOR_CLASSES.get(minor, f"Phone ({minor})")
        return f"Phone ({sub})"

    if major == 0x01:  # Computer
        return "Computer"
    if major == 0x05:  # Peripheral
        return "Peripheral (Input Device)"
    if major == 0x06:  # Imaging
        return "Imaging (Printer/Scanner)"
    if major == 0x07:  # Wearable
        return "Wearable (Watch/Tracker)"
    if major == 0x08:  # Toy
        return "Toy"
    if major == 0x09:  # Health
        return "Health Device"

    return MAJOR_DEVICE_CLASSES.get(major, f"Device Class ({major})")


def is_resolvable_private_address(mac_address: str) -> bool:
    """Return True if the MAC address is a BLE Resolvable Private Address (RPA).

    In Bluetooth Core Spec, an RPA has the two most significant bits set to 01
    (i.e. (most_significant_byte & 0b11000000) == 0b01000000).
    """
    if not mac_address:
        return False
    try:
        first_byte = int(mac_address.split(":")[0], 16)
        return (first_byte & 0xC0) == 0x40
    except (ValueError, IndexError):
        return False
