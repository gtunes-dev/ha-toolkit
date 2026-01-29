"""Media player platform for FiiO K17."""

from __future__ import annotations

import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .client import FiiOK17Client
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FiiO K17 media player from a config entry."""
    client: FiiOK17Client = hass.data[DOMAIN][entry.entry_id]
    host = entry.data[CONF_HOST]

    async_add_entities([FiiOK17MediaPlayer(client, host)])


class FiiOK17MediaPlayer(MediaPlayerEntity):
    """Representation of a FiiO K17 media player."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name only
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
    )

    def __init__(self, client: FiiOK17Client, host: str) -> None:
        """Initialize the media player."""
        self._client = client
        self._host = host
        self._attr_unique_id = f"fiio_k17_{host}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": f"FiiO K17 ({host})",
            "manufacturer": "FiiO",
            "model": "K17",
        }

        # Register callbacks for device events
        self._client.on_volume_change = self._on_volume_change
        self._client.on_disconnect = self._on_disconnect

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return self._client.connected

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        # Device is always "on" when connected (no power control)
        if self._client.connected:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def volume_level(self) -> float | None:
        """Return volume level (0.0 to 1.0)."""
        if not self._client.connected:
            return None
        return self._client.volume / 100.0

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        volume_int = round(volume * 100)
        success = await self._client.set_volume(volume_int)
        if not success:
            _LOGGER.warning("Failed to set volume to %d", volume_int)
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Increase volume by 1."""
        current = self._client.volume
        if current < 100:
            success = await self._client.set_volume(current + 1)
            if not success:
                _LOGGER.warning("Failed to increase volume")
            self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Decrease volume by 1."""
        current = self._client.volume
        if current > 0:
            success = await self._client.set_volume(current - 1)
            if not success:
                _LOGGER.warning("Failed to decrease volume")
            self.async_write_ha_state()

    @callback
    def _on_volume_change(self, volume: int) -> None:
        """Handle volume change from device (knob turned)."""
        self.async_write_ha_state()

    @callback
    def _on_disconnect(self) -> None:
        """Handle disconnect from device."""
        _LOGGER.warning("FiiO K17 at %s disconnected", self._host)
        self.async_write_ha_state()
