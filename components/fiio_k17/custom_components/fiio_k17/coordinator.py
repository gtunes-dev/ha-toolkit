"""Data update coordinator for FiiO K17."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import DeviceBusyError, DeviceUnreachableError, FiiOK17Client, K17State
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Each poll holds the device for a few tens of ms. While we're disconnected, knob
# changes only reach HA at the next poll, so keep this short.
POLL_INTERVAL = timedelta(seconds=10)

# Consecutive unreachable polls before the entity goes unavailable
OFFLINE_THRESHOLD = 3


class FiiOK17Coordinator(DataUpdateCoordinator[K17State]):
    """Polls the K17 and applies the changes it pushes while connected."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: FiiOK17Client) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {client.host}",
            update_interval=POLL_INTERVAL,
        )
        self.client = client
        self._unreachable_count = 0
        client.on_update = self.async_set_updated_data

    async def _async_update_data(self) -> K17State:
        """Poll the device."""
        try:
            state = await self.client.refresh()
        except DeviceBusyError as err:
            # Another app (e.g. FiiO Control) holds the device. It's still there,
            # so keep showing the last known state.
            if self.data is not None:
                _LOGGER.debug("%s", err)
                return self.data
            raise UpdateFailed(str(err)) from err
        except DeviceUnreachableError as err:
            self._unreachable_count += 1
            if self.data is not None and self._unreachable_count < OFFLINE_THRESHOLD:
                _LOGGER.debug("%s (%d in a row)", err, self._unreachable_count)
                return self.data
            raise UpdateFailed(str(err)) from err
        self._unreachable_count = 0
        return state
