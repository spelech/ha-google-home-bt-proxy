"""Tests for runtime state and settings persistence across restarts and reloads."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.google_home_bt_proxy import (
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.google_home_bt_proxy.const import (
    CONF_GLOBAL_SCANNING_ENABLED,
    CONF_PAUSED_SPEAKERS,
    CONF_SCAN_INTERVAL,
    DOMAIN,
)
from custom_components.google_home_bt_proxy.models import (
    GlobalProxyState,
    SpeakerNode,
    SpeakerProxyState,
)
from custom_components.google_home_bt_proxy.persistence import (
    ProxyStateStore,
    update_options_in_place,
)


def test_speaker_proxy_state_serialization_roundtrip():
    """Verify SpeakerProxyState serializes and restores operational metrics safely."""
    state = SpeakerProxyState(
        enabled=False,
        total_advertisements=150,
        filtered_advertisements=25,
        last_scan_count=8,
        last_scan_duration=4.2,
        last_scan_timestamp=1700001234.5,
    )
    snap = state.to_persisted_dict()

    restored = SpeakerProxyState()
    restored.restore_persisted_dict(snap)
    assert restored.total_advertisements == 150
    assert restored.filtered_advertisements == 25
    assert restored.last_scan_count == 8
    assert restored.last_scan_duration == 4.2
    assert restored.last_scan_timestamp == 1700001234.5

    # Ignores invalid payloads without raising
    restored.restore_persisted_dict("not-a-dict")  # type: ignore[arg-type]
    assert restored.total_advertisements == 150


@pytest.mark.asyncio
async def test_proxy_state_store_roundtrip_real_hass(tmp_path):
    """Verify ProxyStateStore saves and reloads global and speaker state on disk."""
    hass = HomeAssistant(str(tmp_path))
    store = ProxyStateStore(hass, "entry-persist-1")

    global_state = GlobalProxyState(enabled=False)
    spk_state = SpeakerProxyState(
        enabled=False,
        total_advertisements=88,
        filtered_advertisements=12,
        last_scan_count=5,
        last_scan_duration=3.5,
        last_scan_timestamp=1700005000.0,
    )
    speakers_data = {
        "spk-1": {
            "speaker": SpeakerNode("spk-1", "Office", "192.168.1.20", "tok"),
            "state": spk_state,
        }
    }

    await store.async_save_now(global_state, speakers_data)

    store2 = ProxyStateStore(hass, "entry-persist-1")
    loaded = await store2.async_load()
    assert loaded["global"]["enabled"] is False
    assert loaded["speakers"]["spk-1"]["enabled"] is False
    assert loaded["speakers"]["spk-1"]["total_advertisements"] == 88
    assert loaded["speakers"]["spk-1"]["filtered_advertisements"] == 12
    assert loaded["speakers"]["spk-1"]["last_scan_count"] == 5
    assert loaded["speakers"]["spk-1"]["last_scan_duration"] == 3.5
    assert loaded["speakers"]["spk-1"]["last_scan_timestamp"] == 1700005000.0
    await hass.async_stop()


@pytest.mark.asyncio
async def test_proxy_state_store_handles_mock_hass():
    """Verify ProxyStateStore safely no-ops when hass has no real event loop."""
    mock_hass = MagicMock()
    store = ProxyStateStore(mock_hass, "entry-mock")
    assert await store.async_load() == {}
    await store.async_save_now(GlobalProxyState(), {})
    store.schedule_save(GlobalProxyState(), {})


@pytest.mark.asyncio
async def test_in_place_toggle_options_persist_and_avoid_reload():
    """Verify toggling switches updates entry.options in-place without reloading the integration."""
    mock_hass = MagicMock()
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Google Home Bluetooth Proxy",
        data={},
        options={CONF_SCAN_INTERVAL: 6},
        source=SOURCE_USER,
        unique_id="persist-uid-1",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )

    def _fake_update_entry(target_entry, *, options=None, data=None):
        if options is not None:
            object.__setattr__(target_entry, "options", MappingProxyType(dict(options)))

    mock_hass.config_entries.async_update_entry.side_effect = _fake_update_entry
    mock_hass.data = {DOMAIN: {entry.entry_id: {"speakers": {}}}}

    # Pause spk-2 and disable global scanning in-place
    update_options_in_place(mock_hass, entry, speaker_id="spk-2", speaker_enabled=False)
    update_options_in_place(mock_hass, entry, global_scanning_enabled=False)

    assert entry.options[CONF_PAUSED_SPEAKERS] == ["spk-2"]
    assert entry.options[CONF_GLOBAL_SCANNING_ENABLED] is False
    assert entry.options[CONF_SCAN_INTERVAL] == 6

    with (
        patch("custom_components.google_home_bt_proxy.async_unload_entry", AsyncMock()) as m_unload,
        patch("custom_components.google_home_bt_proxy.async_setup_entry", AsyncMock()) as m_setup,
    ):
        # In-place update must NOT trigger full integration reload
        await async_reload_entry(mock_hass, entry)
        m_unload.assert_not_called()
        m_setup.assert_not_called()

        # Simulate an OptionsFlow edit changing scan_interval -> MUST trigger reload
        object.__setattr__(
            entry,
            "options",
            MappingProxyType({**entry.options, CONF_SCAN_INTERVAL: 10}),
        )
        await async_reload_entry(mock_hass, entry)
        m_unload.assert_awaited_once_with(mock_hass, entry)
        m_setup.assert_awaited_once_with(mock_hass, entry)


@pytest.mark.asyncio
async def test_full_reload_preserves_paused_speakers_global_toggle_and_counters(tmp_path):
    """Verify async_unload_entry + async_setup_entry preserves toggles and operational counters."""
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    entry = ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Google Home Bluetooth Proxy",
        data={},
        options={
            CONF_PAUSED_SPEAKERS: ["spk-2"],
            CONF_GLOBAL_SCANNING_ENABLED: True,
        },
        source=SOURCE_USER,
        unique_id="reload-uid-1",
        discovery_keys=MappingProxyType({}),
        subentries_data=None,
    )

    spk1 = SpeakerNode("spk-1", "Living Room", "192.168.1.50", "tok-1")
    spk2 = SpeakerNode("spk-2", "Kitchen Mini", "192.168.1.51", "tok-2")

    def _create_bg_task(coro, name=None):
        coro.close()
        return MagicMock()

    with (
        patch.object(hass, "async_create_background_task", side_effect=_create_bg_task),
        patch(
            "custom_components.google_home_bt_proxy.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.google_home_bt_proxy.zeroconf.async_get_instance", AsyncMock()),
        patch(
            "custom_components.google_home_bt_proxy.GoogleHomeProxyCoordinator"
        ) as mock_coord_cls,
        patch(
            "custom_components.google_home_bt_proxy.bluetooth.async_register_scanner",
            return_value=MagicMock(),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch.object(hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)),
    ):
        mock_coord_cls.return_value.async_get_speakers = AsyncMock(return_value=[spk1, spk2])

        assert await async_setup_entry(hass, entry) is True
        entry_data = hass.data[DOMAIN][entry.entry_id]
        assert entry_data["speakers"]["spk-1"]["state"].enabled is True
        assert entry_data["speakers"]["spk-1"]["state"].status == "idle"
        assert entry_data["speakers"]["spk-2"]["state"].enabled is False
        assert entry_data["speakers"]["spk-2"]["state"].status == "disabled"

        # Accumulate operational metrics before unload
        entry_data["speakers"]["spk-1"]["state"].total_advertisements = 42
        entry_data["speakers"]["spk-1"]["state"].filtered_advertisements = 7
        entry_data["speakers"]["spk-1"]["state"].last_scan_count = 3
        entry_data["speakers"]["spk-1"]["state"].last_scan_duration = 4.0
        entry_data["speakers"]["spk-1"]["state"].last_scan_timestamp = 1700009999.0

        assert await async_unload_entry(hass, entry) is True

        # Setup again (simulating reload or HA restart)
        assert await async_setup_entry(hass, entry) is True
        reloaded_data = hass.data[DOMAIN][entry.entry_id]
        assert reloaded_data["speakers"]["spk-1"]["state"].enabled is True
        assert reloaded_data["speakers"]["spk-1"]["state"].total_advertisements == 42
        assert reloaded_data["speakers"]["spk-1"]["state"].filtered_advertisements == 7
        assert reloaded_data["speakers"]["spk-1"]["state"].last_scan_count == 3
        assert reloaded_data["speakers"]["spk-1"]["state"].last_scan_timestamp == 1700009999.0
        assert reloaded_data["speakers"]["spk-2"]["state"].enabled is False
        assert reloaded_data["speakers"]["spk-2"]["state"].status == "disabled"

        await async_unload_entry(hass, entry)
    await hass.async_stop()
