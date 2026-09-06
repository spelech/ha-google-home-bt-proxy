"""Unit tests for signal processing, RSSI smoothing, and BLE device filtering."""

from custom_components.google_home_bt_proxy.const import (
    FILTER_MODE_ALL,
    FILTER_MODE_KNOWN_ONLY,
    FILTER_MODE_WHITELIST,
    RSSI_FILTER_EMA,
    RSSI_FILTER_MEDIAN,
    RSSI_FILTER_NONE,
)
from custom_components.google_home_bt_proxy.filter import (
    RssiSmoothingFilter,
    SignalProcessor,
    calculate_distance,
)
from custom_components.google_home_bt_proxy.models import DiscoveredDevice

# ---------------------------------------------------------------------------
# Distance Calculation Tests
# ---------------------------------------------------------------------------


def test_calculate_distance_reference_power():
    """At reference power (-59 dBm @ 1m), calculated distance should be exactly 1.0m."""
    dist = calculate_distance(rssi=-59, ref_power=-59, path_loss_exponent=2.0)
    assert dist == 1.0


def test_calculate_distance_known_values():
    """Test standard log-distance path loss values."""
    # Free space (n = 2.0), 6 dB drop = doubling of distance
    # -59 - 6 = -65 dBm -> ~2.0m
    dist_free_space = calculate_distance(rssi=-65, ref_power=-59, path_loss_exponent=2.0)
    assert 1.9 <= dist_free_space <= 2.1

    # Indoor environment (n = 2.5)
    dist_indoor = calculate_distance(rssi=-75, ref_power=-59, path_loss_exponent=2.5)
    assert 4.0 <= dist_indoor <= 5.0

    # Attenuated RSSI (-90 dBm)
    dist_far = calculate_distance(rssi=-90, ref_power=-59, path_loss_exponent=2.5)
    assert dist_far > 15.0


def test_calculate_distance_edge_cases():
    """Verify edge case handling: positive RSSI, zero exponent, overflow."""
    # Positive RSSI clamped/treated as 0.0m
    assert calculate_distance(rssi=5) == 0.0
    assert calculate_distance(rssi=0) == 0.0

    # Negative or zero path loss exponent falls back to 2.0
    dist_zero_n = calculate_distance(rssi=-65, ref_power=-59, path_loss_exponent=0.0)
    dist_fallback = calculate_distance(rssi=-65, ref_power=-59, path_loss_exponent=2.0)
    assert dist_zero_n == dist_fallback

    # Extreme value does not raise OverflowError
    dist_overflow = calculate_distance(rssi=-10000, ref_power=-10, path_loss_exponent=0.01)
    assert dist_overflow == 999.99


# ---------------------------------------------------------------------------
# RSSI Smoothing Filter Tests
# ---------------------------------------------------------------------------


def test_rssi_smoothing_filter_none():
    """Verify RSSI_FILTER_NONE passes through raw values with count 1."""
    smoother = RssiSmoothingFilter(mode=RSSI_FILTER_NONE)
    val, count = smoother.filter("AA:BB:CC:DD:EE:FF", -70)
    assert val == -70
    assert count == 1

    val, count = smoother.filter("AA:BB:CC:DD:EE:FF", -80)
    assert val == -80
    assert count == 1


def test_rssi_smoothing_filter_median():
    """Verify median smoothing over a rolling window."""
    smoother = RssiSmoothingFilter(mode=RSSI_FILTER_MEDIAN, window_size=3)
    mac = "11:22:33:44:55:66"

    # Sample 1: only 1 sample
    val1, count1 = smoother.filter(mac, -70, now=10.0)
    assert val1 == -70
    assert count1 == 1

    # Sample 2: median of [-70, -80] = -75
    val2, count2 = smoother.filter(mac, -80, now=11.0)
    assert val2 == -75
    assert count2 == 2

    # Sample 3: median of [-70, -80, -60] -> sorted [-80, -70, -60] -> -70
    val3, count3 = smoother.filter(mac, -60, now=12.0)
    assert val3 == -70
    assert count3 == 3

    # Sample 4: window is 3, so [-70] drops off.
    # Window is now [-80, -60, -90] -> sorted [-90, -80, -60] -> -80
    val4, count4 = smoother.filter(mac, -90, now=13.0)
    assert val4 == -80
    assert count4 == 3


def test_rssi_smoothing_filter_ema():
    """Verify exponential moving average smoothing."""
    smoother = RssiSmoothingFilter(mode=RSSI_FILTER_EMA, window_size=5, ema_alpha=0.5)
    mac = "AA:11:22:33:44:55"

    # Sample 1: single sample
    val1, count1 = smoother.filter(mac, -60, now=1.0)
    assert val1 == -60
    assert count1 == 1

    # Sample 2: ema = 0.5 * (-80) + 0.5 * (-60) = -70
    val2, count2 = smoother.filter(mac, -80, now=2.0)
    assert val2 == -70
    assert count2 == 2

    # Sample 3: ema = 0.5 * (-60) + 0.5 * (-70) = -65
    val3, count3 = smoother.filter(mac, -60, now=3.0)
    assert val3 == -65
    assert count3 == 3


def test_rssi_smoothing_filter_expiration():
    """Verify samples older than max_age are pruned."""
    smoother = RssiSmoothingFilter(mode=RSSI_FILTER_MEDIAN, window_size=5, max_age=10.0)
    mac = "DE:AD:BE:EF:00:01"

    smoother.filter(mac, -70, now=100.0)
    smoother.filter(mac, -80, now=105.0)

    # Next sample at 112.0s: first sample (100.0s) pruned (12s > 10s); second sample kept
    val, count = smoother.filter(mac, -60, now=112.0)
    # Remaining samples are [-80, -60], median is -70
    assert val == -70
    assert count == 2


def test_rssi_smoothing_filter_clear():
    """Verify clear resets history."""
    smoother = RssiSmoothingFilter(mode=RSSI_FILTER_MEDIAN, window_size=3)
    mac = "AA:BB:CC:11:22:33"

    smoother.filter(mac, -70)
    smoother.filter(mac, -80)
    smoother.clear()

    # After clear, next sample should be treated as 1st sample
    val, count = smoother.filter(mac, -60)
    assert val == -60
    assert count == 1


# ---------------------------------------------------------------------------
# SignalProcessor & Filtering Tests
# ---------------------------------------------------------------------------


def test_signal_processor_all_mode():
    """Verify FILTER_MODE_ALL allows both named and unnamed devices."""
    proc = SignalProcessor(filter_mode=FILTER_MODE_ALL, rssi_offset=0)

    named_dev = DiscoveredDevice(mac_address="11:22:33:44:55:66", rssi=-70, name="Smart Bulb")
    unnamed_dev = DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:FF", rssi=-85, name=None)

    res1 = proc.process(named_dev)
    assert res1.is_allowed is True
    assert res1.filtered_rssi == -70
    assert res1.raw_rssi == -70

    res2 = proc.process(unnamed_dev)
    assert res2.is_allowed is True
    assert res2.filtered_rssi == -85


def test_signal_processor_rssi_offset():
    """Verify hardware calibration offset is correctly applied."""
    proc = SignalProcessor(rssi_offset=5)
    dev = DiscoveredDevice(mac_address="11:22:33:44:55:66", rssi=-75)

    res = proc.process(dev)
    assert res.raw_rssi == -75
    assert res.calibrated_rssi == -70
    assert res.filtered_rssi == -70


def test_signal_processor_max_distance_cutoff():
    """Verify advertisements exceeding max_distance are rejected."""
    # ref_power=-59, n=2.0: -59 dBm is 1m, -75 dBm is ~6.3m
    proc = SignalProcessor(
        max_distance=5.0,
        ref_power=-59,
        path_loss_exponent=2.0,
    )

    close_dev = DiscoveredDevice(mac_address="11:11:11:11:11:11", rssi=-65)  # ~2.0m <= 5.0m
    far_dev = DiscoveredDevice(mac_address="22:22:22:22:22:22", rssi=-80)  # ~11.2m > 5.0m

    res_close = proc.process(close_dev)
    assert res_close.is_allowed is True
    assert res_close.estimated_distance <= 5.0

    res_far = proc.process(far_dev)
    assert res_far.is_allowed is False
    assert "Exceeds max distance" in (res_far.filter_reason or "")
    assert res_far.estimated_distance > 5.0


def test_signal_processor_whitelist_mac_and_prefix():
    """Verify whitelist mode matches exact MAC and MAC prefixes."""
    proc = SignalProcessor(
        filter_mode=FILTER_MODE_WHITELIST,
        tracked_devices=["AA:BB:CC", "11:22:33:44:55:66"],
    )

    exact_match = DiscoveredDevice(mac_address="11:22:33:44:55:66", rssi=-70)
    prefix_match = DiscoveredDevice(mac_address="AA:BB:CC:99:88:77", rssi=-72)
    no_match = DiscoveredDevice(mac_address="FF:EE:DD:00:11:22", rssi=-65)

    assert proc.process(exact_match).is_allowed is True
    assert proc.process(prefix_match).is_allowed is True
    res_no = proc.process(no_match)
    assert res_no.is_allowed is False
    assert "Not in tracked whitelist" in (res_no.filter_reason or "")


def test_signal_processor_whitelist_name():
    """Verify whitelist mode matches local names."""
    proc = SignalProcessor(
        filter_mode=FILTER_MODE_WHITELIST,
        tracked_devices=["BEACON", "TILE"],
    )

    beacon_dev = DiscoveredDevice(
        mac_address="11:22:33:44:55:66", rssi=-70, name="Living Room Beacon"
    )
    tile_dev = DiscoveredDevice(mac_address="22:33:44:55:66:77", rssi=-75, name="Tile Pro")
    other_dev = DiscoveredDevice(mac_address="33:44:55:66:77:88", rssi=-68, name="Fitness Tracker")

    assert proc.process(beacon_dev).is_allowed is True
    assert proc.process(tile_dev).is_allowed is True
    assert proc.process(other_dev).is_allowed is False


def test_signal_processor_known_only_mode():
    """Verify known_only mode allows named or IRK-resolved devices, rejecting ephemeral MACs."""
    proc = SignalProcessor(
        filter_mode=FILTER_MODE_KNOWN_ONLY,
        tracked_devices=["AA:BB:CC:DD:EE:FF"],
    )

    named_dev = DiscoveredDevice(mac_address="11:22:33:44:55:66", rssi=-70, name="Headphones")
    unnamed_rpa = DiscoveredDevice(
        mac_address="44:55:66:77:88:99", rssi=-75, name=None, is_rpa=True
    )
    unnamed_in_tracked = DiscoveredDevice(mac_address="AA:BB:CC:DD:EE:FF", rssi=-80, name=None)
    unnamed_random = DiscoveredDevice(mac_address="99:88:77:66:55:44", rssi=-82, name=None)

    # 1. Named device: allowed
    assert proc.process(named_dev).is_allowed is True

    # 2. Unnamed RPA with resolved identity: allowed
    assert proc.process(unnamed_rpa, resolved_identity="Steve's iPhone").is_allowed is True

    # 3. Unnamed RPA without resolved identity: rejected
    res_unresolved = proc.process(unnamed_rpa, resolved_identity=None)
    assert res_unresolved.is_allowed is False
    assert "Unnamed ephemeral address" in (res_unresolved.filter_reason or "")

    # 4. Unnamed device in tracked whitelist: allowed
    assert proc.process(unnamed_in_tracked).is_allowed is True

    # 5. Unnamed random device not tracked: rejected
    assert proc.process(unnamed_random).is_allowed is False


def test_signal_processor_unknown_modes_and_empty_tracked():
    """Verify fallback behavior with unknown modes and empty whitelist."""
    # Unknown RSSI filter mode returns rssi and count
    smoother = RssiSmoothingFilter(mode="unknown_algorithm")
    smoother.filter("AA:BB:CC:11:22:33", -70)
    val, count = smoother.filter("AA:BB:CC:11:22:33", -75)
    assert val == -75
    assert count == 2

    # Whitelist mode with empty tracked_devices rejects all devices
    proc_empty = SignalProcessor(filter_mode=FILTER_MODE_WHITELIST, tracked_devices=[])
    dev = DiscoveredDevice(mac_address="11:22:33:44:55:66", rssi=-70)
    assert proc_empty.process(dev).is_allowed is False

    # Unknown filter mode falls back to allowed
    proc_unknown = SignalProcessor(filter_mode="unknown_filter_mode")
    assert proc_unknown.process(dev).is_allowed is True
