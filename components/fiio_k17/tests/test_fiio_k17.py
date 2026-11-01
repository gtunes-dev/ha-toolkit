"""Integration tests for fiio_k17 against a fake K17 server."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.fiio_k17 import client as client_mod
from custom_components.fiio_k17.const import DOMAIN

ENTITY = "media_player.fiio_k17"


async def setup_integration(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "127.0.0.1"}, title="FiiO K17")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, hass.data[DOMAIN][entry.entry_id]


async def call(hass, service, **data):
    await hass.services.async_call(
        "media_player", service, {"entity_id": ENTITY, **data}, blocking=True
    )


async def test_setup_and_poll_releases_connection(hass, fake_k17, patch_port):
    entry, coordinator = await setup_integration(hass)
    st = hass.states.get(ENTITY)
    assert st.state == STATE_ON
    assert st.attributes["volume_level"] == 0.2
    assert st.attributes["source"] == "USB"
    assert "Local Play" in st.attributes["source_list"]
    # Poll (hold=0) closes right away, cleanly
    await asyncio.sleep(0.1)
    assert not coordinator.client.connected
    assert fake_k17.closed_cleanly == fake_k17.connections == 1
    await hass.config_entries.async_unload(entry.entry_id)


async def test_commands_hold_connection_and_receive_pushes(hass, fake_k17, patch_port):
    with patch.object(client_mod, "IDLE_TIMEOUT", 0.5):
        entry, coordinator = await setup_integration(hass)
        await asyncio.sleep(0.1)

        # Knob turned while disconnected: volume_up must read fresh volume first
        fake_k17.volume = 40
        await call(hass, "volume_up")
        assert fake_k17.volume == 41
        assert hass.states.get(ENTITY).attributes["volume_level"] == 0.41

        await call(hass, "volume_set", volume_level=0.3)
        assert fake_k17.volume == 30
        assert coordinator.client.connected  # held after a command

        # Pushes while connected reach the entity
        fake_k17.push_volume(35)
        fake_k17.push_input("0003")
        await asyncio.sleep(0.05)
        await hass.async_block_till_done()
        st = hass.states.get(ENTITY)
        assert st.attributes["volume_level"] == 0.35
        assert st.attributes["source"] == "Coaxial"

        # Idle release
        await asyncio.sleep(0.8)
        assert not coordinator.client.connected
        assert fake_k17.connections == 2  # one poll, one held command session
        assert fake_k17.closed_cleanly == 2
        await hass.config_entries.async_unload(entry.entry_id)


async def test_select_source(hass, fake_k17, patch_port):
    entry, _ = await setup_integration(hass)
    await call(hass, "select_source", source="Optical")
    assert fake_k17.input == "0002"
    assert hass.states.get(ENTITY).attributes["source"] == "Optical"
    # Already on Optical: nothing sent
    n = len(fake_k17.requests)
    await call(hass, "select_source", source="Optical")
    assert not any(r.startswith("0657") for r in fake_k17.requests[n:])
    await hass.config_entries.async_unload(entry.entry_id)


async def test_select_source_retries_after_lockout(hass, fake_k17, patch_port):
    entry, _ = await setup_integration(hass)
    orig = fake_k17._reply
    ignored = []

    def reply(req, writer):
        if req.startswith("0657") and not ignored:  # first switch ignored (lockout)
            ignored.append(req)
            return
        orig(req, writer)

    fake_k17._reply = reply
    with patch.object(client_mod, "INPUT_SWITCH_LOCKOUT", 0.1), patch.object(
        client_mod, "INPUT_SWITCH_TIMEOUT", 0.1
    ):
        await call(hass, "select_source", source="Balanced")
    assert ignored and fake_k17.input == "0005"
    assert hass.states.get(ENTITY).attributes["source"] == "Balanced"
    await hass.config_entries.async_unload(entry.entry_id)


async def test_busy_keeps_state_and_command_errors(hass, fake_k17, patch_port):
    entry, coordinator = await setup_integration(hass)
    fake_k17.busy = True
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    st = hass.states.get(ENTITY)
    assert st.state == STATE_ON
    assert st.attributes["volume_level"] == 0.2
    with pytest.raises(HomeAssistantError, match="in use by another app"):
        await call(hass, "volume_set", volume_level=0.5)
    assert not coordinator.client.connected
    await hass.config_entries.async_unload(entry.entry_id)


async def test_unreachable_goes_unavailable_after_threshold(hass, fake_k17, patch_port):
    entry, coordinator = await setup_integration(hass)
    await fake_k17.stop()
    for _ in range(2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY).state == STATE_ON
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY).state == STATE_UNAVAILABLE
    await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_retries_when_busy(hass, fake_k17, patch_port):
    fake_k17.busy = True
    entry = MockConfigEntry(domain=DOMAIN, data={"host": "127.0.0.1"}, title="FiiO K17")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_flow_busy(hass, fake_k17, patch_port):
    fake_k17.busy = True
    with patch(
        "custom_components.fiio_k17.config_flow.FiiOK17Client",
        lambda host: client_mod.FiiOK17Client(host, fake_k17.port),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "127.0.0.1"}
        )
    assert result["errors"] == {"base": "device_busy"}


@pytest.mark.skipif("not config.getoption('--live-host')")
async def test_live_device(hass, socket_enabled, request):
    """Smoke test against a real K17 (pytest --live-host IP).

    Re-sets the current volume and source, so nothing audible changes. Disable the
    integration in your HA instance and close the FiiO app first.
    """
    import pytest_socket

    host = request.config.getoption("--live-host")
    pytest_socket.socket_allow_hosts(["127.0.0.1", host])
    entry = MockConfigEntry(domain=DOMAIN, data={"host": host}, title="FiiO K17")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    st = hass.states.get(ENTITY)
    assert st.state == STATE_ON and st.attributes["volume_level"] is not None
    # Re-set current volume and current source (no audible change)
    await call(hass, "volume_set", volume_level=st.attributes["volume_level"])
    await call(hass, "select_source", source=st.attributes["source"])
    await hass.config_entries.async_unload(entry.entry_id)
