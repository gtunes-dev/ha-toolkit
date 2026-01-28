"""FiiO K17 client implementation."""

import socket
import json
import threading
from typing import Callable, Optional


class FiiOK17:
    """Control interface for FiiO K17 DAC/Amp."""

    PORT = 12100

    def __init__(self, host: str):
        self.host = host
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.settings: dict = {}
        self._listen_thread: Optional[threading.Thread] = None
        self._stop_listening = False

        # Callbacks
        self.on_volume_change: Optional[Callable[[int], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None

    def connect(self) -> dict:
        """
        Connect to the K17 and perform handshake.
        Returns the device settings.
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.host, self.PORT))
        self.connected = True

        # Handshake sequence
        self._send_command("0599000c0000")  # INIT
        self._recv_response()  # ACK

        self._send_command("05010008")  # GET_SETTINGS
        settings_response = self._recv_response()

        # Parse JSON from settings response
        # Format: a501009C{...json...}
        if '{' in settings_response:
            json_start = settings_response.index('{')
            json_str = settings_response[json_start:]
            self.settings = json.loads(json_str)

        return self.settings

    def disconnect(self):
        """Close the connection."""
        self._stop_listening = True
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
        if self.sock:
            self.sock.close()
            self.sock = None
        self.connected = False

    def get_settings(self) -> dict:
        """Get current device settings."""
        self._send_command("05010008")
        response = self._recv_response()

        if '{' in response:
            json_start = response.index('{')
            json_str = response[json_start:]
            self.settings = json.loads(json_str)

        return self.settings

    def get_volume(self) -> int:
        """Get current volume level (0-100)."""
        settings = self.get_settings()
        return settings.get('currentVolume', 0)

    def set_volume(self, volume: int) -> bool:
        """
        Set volume level.

        Args:
            volume: Volume level 0-100

        Returns:
            True if acknowledged
        """
        if not 0 <= volume <= 100:
            raise ValueError("Volume must be between 0 and 100")

        # Format: 0502000c00XX where XX is volume in hex
        cmd = f"0502000c{volume:04x}"
        self._send_command(cmd)

        # Device may send unsolicited notifications (a60a) before the ack (a502)
        # Read responses until we get the volume ack or timeout
        for _ in range(5):  # Max attempts to find the ack
            response = self._recv_response()
            if response.lower().startswith("a502"):
                # Verify the echoed volume matches
                try:
                    echoed = int(response[-4:], 16)
                    self.settings['currentVolume'] = echoed
                    return echoed == volume
                except ValueError:
                    return True  # Got ack but couldn't parse volume

        return False

    def listen(self, blocking: bool = True):
        """
        Listen for volume changes from the device (e.g., when knob is turned).

        Args:
            blocking: If True, blocks the current thread.
                      If False, starts a background thread.
        """
        if blocking:
            self._listen_loop()
        else:
            self._stop_listening = False
            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listen_thread.start()

    def _listen_loop(self):
        """Internal listen loop for incoming messages."""
        self.sock.settimeout(1.0)  # Allow periodic checks for stop signal

        while not self._stop_listening and self.connected:
            try:
                response = self._recv_response()
                if response:
                    self._handle_push_message(response)
            except socket.timeout:
                continue
            except (ConnectionResetError, BrokenPipeError, OSError):
                self.connected = False
                if self.on_disconnect:
                    self.on_disconnect()
                break

    def _handle_push_message(self, message: str):
        """Handle unsolicited messages from the device."""
        # Volume push: a502000C00XX
        if message.lower().startswith("a502"):
            try:
                volume = int(message[-4:], 16)
                self.settings['currentVolume'] = volume
                if self.on_volume_change:
                    self.on_volume_change(volume)
            except ValueError:
                pass

    def _send_command(self, cmd: str):
        """Send a command (ASCII hex string) to the device."""
        if not self.sock:
            raise ConnectionError("Not connected")

        # Commands are sent as ASCII-encoded hex
        self.sock.sendall(cmd.encode('ascii'))

    def _recv_response(self) -> str:
        """Receive a response from the device."""
        if not self.sock:
            raise ConnectionError("Not connected")

        # Read response - the protocol uses variable-length messages
        # We'll read in chunks and look for complete messages
        data = self.sock.recv(4096)
        if not data:
            raise ConnectionResetError("Connection closed by device")

        return data.decode('ascii', errors='replace')
