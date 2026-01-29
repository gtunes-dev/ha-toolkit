"""Async client for FiiO K17 communication.

This module is standalone - no Home Assistant dependencies.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)

# Protocol constants
DEFAULT_PORT = 12100
CMD_INIT = "0599000c0000"
CMD_GET_SETTINGS = "05010008"
CMD_SET_VOLUME_PREFIX = "0502000c"
RESP_VOLUME = "a502"


class FiiOK17Client:
    """Async client for FiiO K17 DAC/Amp.

    Uses a single reader task to avoid concurrent read issues.
    Commands request responses via a Future that the reader fulfills.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        """Initialize the client."""
        self.host = host
        self.port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._reader_task: asyncio.Task | None = None
        self._settings: dict[str, Any] = {}

        # For command/response coordination
        self._response_future: asyncio.Future[str] | None = None
        self._command_lock = asyncio.Lock()

        # Callbacks
        self.on_volume_change: Callable[[int], None] | None = None
        self.on_disconnect: Callable[[], None] | None = None

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    @property
    def volume(self) -> int:
        """Return current volume."""
        return self._settings.get("currentVolume", 0)

    @property
    def settings(self) -> dict:
        """Return current settings."""
        return self._settings

    async def connect(self) -> dict:
        """Connect to the K17 and perform handshake."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5.0,
            )
            self._connected = True

            # Handshake sequence (before reader task starts)
            await self._send_command(CMD_INIT)
            await self._read_once()  # ACK

            await self._send_command(CMD_GET_SETTINGS)
            settings_response = await self._read_once()

            # Parse JSON from settings response
            self._parse_settings_response(settings_response)

            # Start the single reader task
            self._reader_task = asyncio.create_task(self._reader_loop())

            return self._settings

        except (OSError, asyncio.TimeoutError) as err:
            self._connected = False
            raise ConnectionError(f"Failed to connect to {self.host}:{self.port}") from err

    async def disconnect(self) -> None:
        """Close the connection."""
        self._connected = False

        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass  # Connection already closed
            self._writer = None
            self._reader = None

    async def get_settings(self) -> dict[str, Any]:
        """Get current device settings."""
        response = await self._send_and_receive(CMD_GET_SETTINGS)
        if response:
            self._parse_settings_response(response)
        return self._settings

    def _parse_settings_response(self, response: str) -> None:
        """Parse JSON settings from a response string."""
        if "{" in response:
            json_start = response.index("{")
            json_str = response[json_start:]
            self._settings = json.loads(json_str)

    async def set_volume(self, volume: int) -> bool:
        """Set volume level (0-100).

        Returns True if the volume was set successfully.
        """
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")

        cmd: str | None = f"{CMD_SET_VOLUME_PREFIX}{volume:04x}"

        # The device may send unsolicited notifications (a60a) before the ack.
        # Loop: send command on first iteration, then just read on subsequent ones.
        for _ in range(5):
            response = await self._send_and_receive(cmd)
            cmd = None  # Don't re-send on subsequent iterations

            if response and response.lower().startswith(RESP_VOLUME):
                try:
                    echoed = int(response[-4:], 16)
                    self._settings["currentVolume"] = echoed
                    return echoed == volume
                except ValueError:
                    return True

        _LOGGER.warning("Timeout waiting for volume acknowledgment")
        return False

    async def _send_and_receive(self, cmd: str | None) -> str | None:
        """Send a command and wait for the response.

        Uses a Future that the reader task fulfills.
        """
        async with self._command_lock:
            # Set up future for response
            self._response_future = asyncio.get_running_loop().create_future()

            try:
                if cmd:
                    await self._send_command(cmd)

                # Wait for reader task to deliver response
                response = await asyncio.wait_for(self._response_future, timeout=5.0)
                return response
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout waiting for response")
                return None
            finally:
                self._response_future = None

    async def _reader_loop(self) -> None:
        """Single reader task that handles all incoming messages.

        Routes responses to waiting commands, handles push messages.
        """
        while self._connected:
            try:
                data = await self._reader.read(4096)
                if not data:
                    raise ConnectionResetError("Connection closed by device")

                message = data.decode("ascii", errors="replace")

                # If a command is waiting for a response, deliver it
                if self._response_future and not self._response_future.done():
                    self._response_future.set_result(message)
                else:
                    # No command waiting - this is a push message
                    self._handle_push_message(message)

            except asyncio.CancelledError:
                break
            except (ConnectionResetError, BrokenPipeError, OSError) as err:
                _LOGGER.debug("Connection lost: %s", err)
                self._connected = False
                # Cancel any waiting command
                if self._response_future and not self._response_future.done():
                    self._response_future.set_exception(ConnectionError("Disconnected"))
                if self.on_disconnect:
                    self.on_disconnect()
                break

    def _handle_push_message(self, message: str) -> None:
        """Handle unsolicited messages from the device."""
        if message.lower().startswith(RESP_VOLUME):
            try:
                volume = int(message[-4:], 16)
                self._settings["currentVolume"] = volume
                if self.on_volume_change:
                    self.on_volume_change(volume)
            except ValueError:
                pass

    async def _send_command(self, cmd: str) -> None:
        """Send a command to the device."""
        if not self._writer:
            raise ConnectionError("Not connected")

        self._writer.write(cmd.encode("ascii"))
        await self._writer.drain()

    async def _read_once(self) -> str:
        """Read a single response (used during handshake before reader task starts)."""
        if not self._reader:
            raise ConnectionError("Not connected")

        data = await self._reader.read(4096)
        if not data:
            raise ConnectionResetError("Connection closed by device")

        return data.decode("ascii", errors="replace")
