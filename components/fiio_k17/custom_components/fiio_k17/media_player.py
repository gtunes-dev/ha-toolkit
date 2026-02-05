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
from homeassistant.helpers.device_registry import DeviceInfo
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

    async_add_entities([FiiOK17MediaPlayer(client, entry)])


class FiiOK17MediaPlayer(MediaPlayerEntity):
    """Representation of a FiiO K17 media player."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name only
    # VOLUME_MUTE is advertised for compatibility, but the FiiO K17 protocol
    # does not expose true mute functionality. Mute sets volume to 0.
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(self, client: FiiOK17Client, entry: ConfigEntry) -> None:
        """Initialize the media player."""
        self._client = client
        self._host = entry.data[CONF_HOST]

        # Use entry_id for unique_id (matches Eversolo pattern)
        self._attr_unique_id = f"{entry.entry_id}_media_player"

        # Build device info - use entry_id as identifier, title as name
        device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="FiiO",
            model="K17",
        )
        # Add suggested area if provided during setup
        if area := entry.data.get("area"):
            device_info["suggested_area"] = area

        self._attr_device_info = device_info

        # Register callbacks for device events
        self._client.on_volume_change = self._on_volume_change
        self._client.on_disconnect = self._on_disconnect
        self._client.on_reconnect = self._on_reconnect

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

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if volume is muted (volume is 0).

        Note: The FiiO K17 protocol does not expose true mute functionality.
        Volume 0 is treated as muted.
        """
        if not self._client.connected:
            return None
        return self._client.volume == 0

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute sets volume to 0, unmute is ignored.

        Note: The FiiO K17 protocol does not expose true mute functionality.
        Muting sets volume to 0; unmuting is a no-op (user must adjust volume).
        """
        if mute:
            success = await self._client.set_volume(0)
            if not success:
                _LOGGER.warning("Failed to mute volume")
            self.async_write_ha_state()

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
        _LOGGER.warning("FiiO K17 at %s disconnected, will attempt reconnection", self._host)
        self.async_write_ha_state()

    @callback
    def _on_reconnect(self) -> None:
        """Handle successful reconnection to device."""
        _LOGGER.info("FiiO K17 at %s reconnected", self._host)
        self.async_write_ha_state()
