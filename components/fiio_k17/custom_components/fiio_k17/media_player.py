"""Media player platform for FiiO K17."""

from __future__ import annotations

import logging
from collections.abc import Awaitable

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .client import INPUTS, DeviceBusyError, FiiOK17Error, K17State
from .const import DOMAIN
from .coordinator import FiiOK17Coordinator

_LOGGER = logging.getLogger(__name__)

SOURCE_CODES = {name: code for code, name in INPUTS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up FiiO K17 media player from a config entry."""
    coordinator: FiiOK17Coordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([FiiOK17MediaPlayer(coordinator, entry)])


class FiiOK17MediaPlayer(CoordinatorEntity[FiiOK17Coordinator], MediaPlayerEntity):
    """Representation of a FiiO K17 media player."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name only
    # VOLUME_MUTE is advertised for compatibility, but the FiiO K17 protocol
    # does not expose true mute functionality. Mute sets volume to 0.
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_source_list = list(INPUTS.values())

    def __init__(self, coordinator: FiiOK17Coordinator, entry: ConfigEntry) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._client = coordinator.client

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

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        # Device is always "on" when reachable (no power control)
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Return volume level (0.0 to 1.0)."""
        if self.coordinator.data is None or self.coordinator.data.volume is None:
            return None
        return self.coordinator.data.volume / 100.0

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if volume is muted (volume is 0).

        Note: The FiiO K17 protocol does not expose true mute functionality.
        Volume 0 is treated as muted.
        """
        if self.coordinator.data is None or self.coordinator.data.volume is None:
            return None
        return self.coordinator.data.volume == 0

    @property
    def source(self) -> str | None:
        """Return the current input."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.input_name

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute sets volume to 0, unmute is ignored.

        Note: The FiiO K17 protocol does not expose true mute functionality.
        Muting sets volume to 0; unmuting is a no-op (user must adjust volume).
        """
        if mute:
            await self._run(self._client.set_volume(0))

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level (0.0 to 1.0)."""
        await self._run(self._client.set_volume(round(volume * 100)))

    async def async_volume_up(self) -> None:
        """Increase volume by 1."""
        await self._run(self._client.step_volume(1))

    async def async_volume_down(self) -> None:
        """Decrease volume by 1."""
        await self._run(self._client.step_volume(-1))

    async def async_select_source(self, source: str) -> None:
        """Switch input."""
        if (code := SOURCE_CODES.get(source)) is None:
            raise HomeAssistantError(f"Unknown source: {source}")
        await self._run(self._client.set_input(code))

    async def _run(self, command: Awaitable[K17State]) -> None:
        """Run a device command and publish the resulting state."""
        try:
            state = await command
        except DeviceBusyError as err:
            raise HomeAssistantError(
                "FiiO K17 is in use by another app (e.g. FiiO Control)"
            ) from err
        except FiiOK17Error as err:
            raise HomeAssistantError(f"FiiO K17 command failed: {err}") from err
        self.coordinator.async_set_updated_data(state)
