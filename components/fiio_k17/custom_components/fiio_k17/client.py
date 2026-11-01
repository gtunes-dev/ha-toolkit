"""Async client for FiiO K17 communication.

This module is standalone - no Home Assistant dependencies.

The K17 serves only one TCP client at a time, so this client connects on demand
and closes the connection once it has been idle for a while. While connected it
receives the device's push frames (volume knob, input changes). See
docs/protocol.md for the protocol details this is built on.
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import dataclass, field, replace
from typing import Any, Callable

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 12100

# Requests
CMD_GET_SETTINGS = "05010008"
CMD_GET_INPUT = "0607000c0000"
CMD_SET_VOLUME_PREFIX = "0502000c"
CMD_SET_INPUT_PREFIX = "0657000c"

# Frame keys (prefix + command, lowercase)
KEY_SETTINGS = "a501"
KEY_VOLUME = "a502"
KEY_INPUT = "a607"

HEADER_LEN = 8

INPUTS: dict[str, str] = {
    "0001": "USB",
    "0002": "Optical",
    "0003": "Coaxial",
    "0004": "Line In",
    "0005": "Balanced",
    "0006": "Bluetooth",
    "0007": "Streaming",
    "0008": "Local Play",
}

# Timing (seconds)
IDLE_TIMEOUT = 15  # how long to hold the connection after a command
CONNECT_TIMEOUT = 5
CONNECT_RETRY_WINDOW = 4  # device refuses connects briefly after any client closes
CONNECT_RETRY_DELAY = 0.25
RESPONSE_TIMEOUT = 3  # device replies in ~10 ms; silence means another client holds it
CLOSE_TIMEOUT = 2
INPUT_SWITCH_TIMEOUT = 1  # unanswered switches are checked with a query instead
INPUT_SWITCH_LOCKOUT = 3  # device ignores switches within ~2-3 s of the previous one


class FiiOK17Error(Exception):
    """Base error for K17 communication."""


class DeviceUnreachableError(FiiOK17Error):
    """The device could not be reached or dropped the connection."""


class DeviceBusyError(FiiOK17Error):
    """The device accepted the connection but did not reply.

    This happens when another client (e.g. the FiiO Control app) holds the device.
    """


@dataclass
class K17State:
    """Last known device state."""

    volume: int | None = None
    input_code: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    @property
    def input_name(self) -> str | None:
        """Return the display name of the current input."""
        if self.input_code is None:
            return None
        return INPUTS.get(self.input_code, f"Unknown ({self.input_code})")


class FrameParser:
    """Split the device's byte stream into frames using the header length field.

    Header: 2-char prefix, 2-char command, 4 hex chars of total frame length.
    """

    def __init__(self) -> None:
        self._buf = ""

    def feed(self, data: str) -> list[str]:
        """Add received data and return any complete frames."""
        self._buf += data
        frames: list[str] = []
        while len(self._buf) >= HEADER_LEN:
            try:
                length = int(self._buf[4:HEADER_LEN], 16)
            except ValueError:
                length = 0
            if length < HEADER_LEN:
                _LOGGER.warning("Discarding unparseable data: %r", self._buf[:32])
                self._buf = ""
                break
            if len(self._buf) < length:
                break
            frames.append(self._buf[:length])
            self._buf = self._buf[length:]
        return frames


class FiiOK17Client:
    """Async client for the FiiO K17 DAC/Amp.

    Connects on demand and releases the connection when idle. A single reader task
    per connection parses frames; requests wait for a frame of the expected type.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        """Initialize the client."""
        self.host = host
        self.port = port
        self._state = K17State()
        self._lock = asyncio.Lock()
        self._writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task | None = None
        self._connected = False
        self._pending: tuple[str, asyncio.Future[str]] | None = None
        self._idle_deadline = 0.0
        self._idle_handle: asyncio.TimerHandle | None = None
        self._idle_task: asyncio.Task | None = None

        # Called when the device pushes a change we didn't request (knob, input).
        self.on_update: Callable[[K17State], None] | None = None

    @property
    def state(self) -> K17State:
        """Return a copy of the last known state."""
        return replace(self._state, settings=dict(self._state.settings))

    @property
    def connected(self) -> bool:
        """Return True if a connection is currently open."""
        return self._connected

    async def refresh(self, hold: float = 0) -> K17State:
        """Query settings and current input.

        The connection is closed right away unless `hold` (or a recent command)
        keeps it open.
        """
        async with self._lock:
            await self._exchange(CMD_GET_SETTINGS, KEY_SETTINGS)
            await self._exchange(CMD_GET_INPUT, KEY_INPUT)
            self._extend_idle(hold)
        return self.state

    async def set_volume(self, volume: int) -> K17State:
        """Set volume level (0-100)."""
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")
        async with self._lock:
            await self._exchange(f"{CMD_SET_VOLUME_PREFIX}{volume:04x}", KEY_VOLUME)
            self._extend_idle(IDLE_TIMEOUT)
        return self.state

    async def step_volume(self, delta: int) -> K17State:
        """Change volume relative to the device's current level.

        While disconnected, knob changes aren't pushed to us, so read the current
        level first.
        """
        async with self._lock:
            if not self._connected or self._state.volume is None:
                await self._exchange(CMD_GET_SETTINGS, KEY_SETTINGS)
            current = self._state.volume or 0
            target = max(0, min(100, current + delta))
            if target != current:
                await self._exchange(f"{CMD_SET_VOLUME_PREFIX}{target:04x}", KEY_VOLUME)
            self._extend_idle(IDLE_TIMEOUT)
        return self.state

    async def set_input(self, input_code: str) -> K17State:
        """Switch to the input with the given code (see INPUTS).

        The device doesn't reply to a switch to the current input, and silently
        ignores a switch made within ~3 s of the previous one. Check the current
        input first, and if a switch goes unanswered, check whether it took effect
        and retry once after the lockout.
        """
        if input_code not in INPUTS:
            raise ValueError(f"Unknown input code: {input_code}")
        cmd = f"{CMD_SET_INPUT_PREFIX}{input_code}"
        async with self._lock:
            if not self._connected or self._state.input_code is None:
                await self._exchange(CMD_GET_INPUT, KEY_INPUT)
            for attempt in range(2):
                if self._state.input_code == input_code:
                    break
                if attempt:
                    await asyncio.sleep(INPUT_SWITCH_LOCKOUT)
                if await self._exchange(cmd, KEY_INPUT, INPUT_SWITCH_TIMEOUT, optional=True) is None:
                    await self._exchange(CMD_GET_INPUT, KEY_INPUT)
            self._extend_idle(IDLE_TIMEOUT)
            if self._state.input_code != input_code:
                raise FiiOK17Error(f"K17 did not switch to {INPUTS[input_code]}")
        return self.state

    async def close(self) -> None:
        """Close the connection."""
        async with self._lock:
            await self._close()

    async def _exchange(
        self,
        cmd: str,
        expect: str,
        timeout: float = RESPONSE_TIMEOUT,
        optional: bool = False,
    ) -> str | None:
        """Send a request and wait for a frame of the expected type. Must hold the lock.

        No reply means another client holds the device: close and raise
        DeviceBusyError, unless `optional`, in which case return None.
        Retries once on a fresh connection if the existing one turns out to be dead.
        """
        for attempt in range(2):
            await self._ensure_connected()
            assert self._writer is not None
            future: asyncio.Future[str] = asyncio.get_running_loop().create_future()
            self._pending = (expect, future)
            try:
                self._writer.write(cmd.encode("ascii"))
                await self._writer.drain()
                return await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError as err:
                self._pending = None
                if optional:
                    return None
                await self._close()
                raise DeviceBusyError(
                    f"No reply from {self.host}; another app may be connected"
                ) from err
            except (OSError, ConnectionError) as err:
                self._pending = None  # don't let the reader fail a future nobody awaits
                await self._close()
                if attempt == 0:
                    _LOGGER.debug("Connection dropped (%s), retrying", err)
                    continue
                raise DeviceUnreachableError(f"Lost connection to {self.host}") from err
            finally:
                self._pending = None
        raise AssertionError("unreachable")

    async def _ensure_connected(self) -> None:
        """Open a connection if none is open. Must hold the lock."""
        if self._connected:
            return
        await self._close()  # clean up a connection the device dropped

        loop = asyncio.get_running_loop()
        deadline = loop.time() + CONNECT_RETRY_WINDOW
        while True:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port), CONNECT_TIMEOUT
                )
                break
            except ConnectionRefusedError as err:
                if loop.time() >= deadline:
                    raise DeviceUnreachableError(
                        f"Connection to {self.host}:{self.port} refused"
                    ) from err
                await asyncio.sleep(CONNECT_RETRY_DELAY)
            except (OSError, asyncio.TimeoutError) as err:
                raise DeviceUnreachableError(
                    f"Failed to connect to {self.host}:{self.port}"
                ) from err

        self._writer = writer
        self._connected = True
        self._reader_task = asyncio.create_task(self._read_loop(reader))
        _LOGGER.debug("Connected to FiiO K17 at %s:%d", self.host, self.port)

    async def _close(self) -> None:
        """Close the connection cleanly. Must hold the lock.

        Half-close and let the reader drain until the device's EOF; closing with
        unread data makes the device refuse reconnects for longer.
        """
        if self._idle_handle:
            self._idle_handle.cancel()
            self._idle_handle = None
        self._idle_deadline = 0.0
        writer, task = self._writer, self._reader_task
        self._writer = None
        self._reader_task = None
        self._connected = False
        if writer is None:
            return

        with suppress(OSError, RuntimeError):
            if writer.can_write_eof():
                writer.write_eof()
        if task:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(task, CLOSE_TIMEOUT)
        writer.close()
        with suppress(OSError):
            await writer.wait_closed()
        _LOGGER.debug("Disconnected from FiiO K17 at %s", self.host)

    async def _read_loop(self, reader: asyncio.StreamReader) -> None:
        """Read frames until EOF, dispatching each one."""
        parser = FrameParser()
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                for frame in parser.feed(data.decode("ascii", errors="replace")):
                    self._dispatch(frame)
        except (OSError, ConnectionError) as err:
            _LOGGER.debug("Connection error in reader: %s", err)
        finally:
            self._connected = False
            if self._pending and not self._pending[1].done():
                self._pending[1].set_exception(ConnectionResetError("Connection closed"))

    def _dispatch(self, frame: str) -> None:
        """Update state from a frame and route it to a waiting request or on_update."""
        key = frame[:4].lower()
        payload = frame[HEADER_LEN:]
        try:
            if key == KEY_VOLUME:
                self._state.volume = int(payload, 16)
            elif key == KEY_INPUT:
                self._state.input_code = payload.upper()
            elif key == KEY_SETTINGS:
                self._state.settings = json.loads(payload)
                if (volume := self._state.settings.get("currentVolume")) is not None:
                    self._state.volume = int(volume)
            else:
                _LOGGER.debug("Ignoring frame: %r", frame[:64])
                return
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Malformed %s frame %r: %s", key, frame[:64], err)
            return

        if self._pending and self._pending[0] == key and not self._pending[1].done():
            self._pending[1].set_result(frame)
        elif key in (KEY_VOLUME, KEY_INPUT) and self.on_update:
            self.on_update(self.state)

    def _extend_idle(self, hold: float) -> None:
        """Keep the connection open for at least `hold` more seconds."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + hold
        if self._idle_handle and deadline <= self._idle_deadline:
            return
        self._idle_deadline = max(self._idle_deadline, deadline)
        if self._idle_handle:
            self._idle_handle.cancel()
        self._idle_handle = loop.call_at(self._idle_deadline, self._on_idle)

    def _on_idle(self) -> None:
        self._idle_handle = None
        self._idle_task = asyncio.create_task(self._close_if_idle())

    async def _close_if_idle(self) -> None:
        async with self._lock:
            if self._connected and asyncio.get_running_loop().time() >= self._idle_deadline:
                _LOGGER.debug("Idle; releasing connection to %s", self.host)
                await self._close()
