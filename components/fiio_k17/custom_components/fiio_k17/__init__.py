"""The FiiO K17 integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .client import FiiOK17Client
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up FiiO K17 from a config entry."""
    host = entry.data[CONF_HOST]

    client = FiiOK17Client(host)
    try:
        await client.connect()
    except (ConnectionError, OSError) as err:
        raise ConfigEntryNotReady(f"Unable to connect to {host}") from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client: FiiOK17Client = hass.data[DOMAIN].pop(entry.entry_id)
        await client.disconnect()

    return unload_ok
