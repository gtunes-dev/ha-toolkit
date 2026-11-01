"""Test fixtures: a fake K17 TCP server that behaves like the captures in docs/captures."""

import asyncio
import json
from unittest.mock import patch

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


def pytest_addoption(parser):
    parser.addoption("--live-host", metavar="IP", help="also run a smoke test against a real K17")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeK17:
    """Single-client K17 emulator."""

    def __init__(self) -> None:
        self.volume = 20
        self.input = "0001"
        self.busy = False  # accept connections but never reply (another app holds it)
        self.writers: list[asyncio.StreamWriter] = []
        self.connections = 0
        self.closed_cleanly = 0
        self.requests: list[str] = []
        self.server: asyncio.Server | None = None
        self.port = 0

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for w in list(self.writers):
            w.close()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None

    def _frame(self, key: str, payload: str) -> bytes:
        return f"{key}{8 + len(payload):04X}{payload}".encode()

    def push_volume(self, volume: int) -> None:
        self.volume = volume
        for w in self.writers:
            w.write(self._frame("a502", f"{volume:04X}"))

    def push_input(self, code: str) -> None:
        self.input = code
        for w in self.writers:
            w.write(self._frame("a607", code))

    async def _handle(self, reader, writer) -> None:
        self.connections += 1
        self.writers.append(writer)
        buf = ""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    self.closed_cleanly += 1
                    break
                buf += data.decode()
                while len(buf) >= 8 and len(buf) >= int(buf[4:8], 16):
                    n = int(buf[4:8], 16)
                    req, buf = buf[:n], buf[n:]
                    self.requests.append(req)
                    if not self.busy:
                        self._reply(req.lower(), writer)
        except ConnectionError:
            pass
        finally:
            self.writers.remove(writer)
            writer.close()

    def _reply(self, req: str, writer) -> None:
        if req == "05010008":
            body = json.dumps({"currentVolume": self.volume, "maxVolume": 100, "usbAudio": 2},
                              separators=(",", ":"))
            # Settings frame and trailing a60a in one write, like the device often does
            writer.write(self._frame("a501", body) + b"a60a000C000C")
        elif req == "0607000c0000":
            writer.write(self._frame("a607", self.input.upper()))
        elif req.startswith("0502000c"):
            self.volume = int(req[8:], 16)
            writer.write(self._frame("a502", f"{self.volume:04X}"))
        elif req.startswith("0657000c"):
            code = req[8:]
            if code != self.input:  # no reply when already on that input
                self.input = code
                writer.write(self._frame("a607", code.upper()))


@pytest.fixture
async def fake_k17(socket_enabled):
    dev = FakeK17()
    await dev.start()
    yield dev
    await dev.stop()


@pytest.fixture
def patch_port(fake_k17):
    """Point the integration's client at the fake server's port."""
    from custom_components.fiio_k17 import client as client_mod

    real = client_mod.FiiOK17Client

    with patch(
        "custom_components.fiio_k17.FiiOK17Client",
        lambda host: real(host, fake_k17.port),
    ), patch.object(client_mod, "CONNECT_RETRY_WINDOW", 0.3), patch.object(
        client_mod, "RESPONSE_TIMEOUT", 0.3
    ):
        yield
