# FiiO K17 Protocol Reverse Engineering - Complete Documentation

## Project Goal

Build a Home Assistant integration for the FiiO K17 DAC/Amp that exposes volume control and monitoring, allowing HA to automate the device's volume.

## Discovery Method

Protocol was reverse-engineered by capturing TCP traffic between the official FiiO Control macOS app and the K17 device using Wireshark/tcpdump.

---

## Protocol Overview

| Property | Value |
|----------|-------|
| **Transport** | TCP |
| **Port** | 12100 |
| **Encoding** | ASCII-encoded hexadecimal |
| **Connection** | Persistent (device pushes updates to connected clients) |

### Message Format

All messages are ASCII strings representing hexadecimal bytes. For example, the ASCII string `0502000c0025` represents the bytes `05 02 00 0c 00 25`.

#### General Structure

```
[prefix][command][flags/reserved][length?][payload...]

- Prefix: 05 = request, 06 = request (alternate), a5 = response/ack, a6 = unsolicited push
- Command: 1 byte identifying the operation
- The remaining bytes vary by command
```

---

## Connection &amp; Handshake Sequence

When the FiiO app connects to the K17, it performs this initialization sequence:

### Step 1: INIT (Command 0x99)
```
Client → K17: 0599000c0000
K17 → Client: a599000C0302
```
- Response may indicate firmware version (3.02?)

### Step 2: GET_SETTINGS (Command 0x01)
```
Client → K17: 05010008
K17 → Client: a501009C{"currentVolume":30,"folderJump":true,"gaplessPlay":true,"maxVolume":100,"memoryPlay":false,"memoryType":0,"playMode":0,"replayGain":0,"usbAudio":2}
```
- Response format: `a501009C` header followed by JSON
- `9C` (156 decimal) appears to be the JSON payload length

### Step 3: Additional Initialization (may be optional for volume-only control)
```
Client → K17: 0607000c0000
K17 → Client: a607000C0007

Client → K17: 062700100000A0A9
K17 → Client: a62700AC... (playlist/track data, mostly zeros if no SD card)

Client → K17: 0639000c0000
K17 → Client: a639000C00FF

Client → K17: 062800100000001E
K17 → Client: a62801C2... (track info data)
```

### Unsolicited Notification During Init
The K17 also pushes this during connection:
```
K17 → Client: a60a000C000C
```
- Command 0x0a with prefix 0xa6 (unsolicited)
- Purpose unknown, possibly a "ready" or "sync" notification

---

## Volume Control

### Set Volume (Client → K17)

**Command:** `0502000c00XX`

| Byte(s) | Value | Meaning |
|---------|-------|---------|
| 0 | `05` | Request prefix |
| 1 | `02` | Command: Set Volume |
| 2-3 | `00 0c` | Fixed (possibly flags + length) |
| 4-5 | `00 XX` | Volume as 16-bit big-endian (0-100) |

**Examples:**
- Set volume to 37: `0502000c0025` (0x25 = 37)
- Set volume to 22: `0502000c0016` (0x16 = 22)
- Set volume to 100: `0502000c0064` (0x64 = 100)

**Response:** `a502000C00XX`
- Same format with prefix changed to `a5` (acknowledgment)
- Echoes the volume value back

### Volume Push Notifications (K17 → Client)

When the physical volume knob is turned, the K17 pushes updates to all connected clients:

```
K17 → Client: a502000C00XX
```

- Same format as the set-volume acknowledgment
- Prefix `a5` with command `02`
- Last two bytes contain the new volume

**Observed behavior:** Updates are sent approximately every 600-700ms as the knob is turned (one message per volume step).

---

## Settings JSON Schema

The GET_SETTINGS command returns this JSON structure:

```json
{
    "currentVolume": 30,      // Current volume level (0-100)
    "maxVolume": 100,         // Maximum volume limit
    "folderJump": true,       // Folder navigation setting
    "gaplessPlay": true,      // Gapless playback enabled
    "memoryPlay": false,      // Resume playback on power-on
    "memoryType": 0,          // Memory type setting
    "playMode": 0,            // Play mode (0=normal, others unknown)
    "replayGain": 0,          // Replay gain setting
    "usbAudio": 2             // USB audio mode (2=UAC2?)
}
```

---

## Commands Reference (Known)

| Cmd | Prefix | Name | Request | Response |
|-----|--------|------|---------|----------|
| `99` | `05`/`a5` | INIT | `0599000c0000` | `a599000C0302` |
| `01` | `05`/`a5` | GET_SETTINGS | `05010008` | `a501009C{json}` |
| `02` | `05`/`a5` | SET_VOLUME | `0502000c00XX` | `a502000C00XX` |
| `02` | `a5` | VOLUME_PUSH | N/A (unsolicited) | `a502000C00XX` |
| `07` | `06`/`a6` | UNKNOWN | `0607000c0000` | `a607000C0007` |
| `27` | `06`/`a6` | GET_PLAYLIST? | `062700100000A0A9` | `a62700AC...` |
| `39` | `06`/`a6` | UNKNOWN | `0639000c0000` | `a639000C00FF` |
| `28` | `06`/`a6` | GET_TRACK_INFO? | `062800100000001E` | `a62801C2...` |
| `0a` | `a6` | NOTIFY? | N/A (unsolicited) | `a60a000C000C` |

---

## Python Proof-of-Concept

A working Python library was created: `fiio_k17.py`

### Key Features
- Connect and perform handshake
- Get device settings (JSON)
- Set volume (0-100)
- Listen for volume push notifications (when knob is turned)
- CLI interface for testing

### Usage

```bash
# Get current volume
python fiio_k17.py 192.168.20.158 --get-volume

# Set volume to 50
python fiio_k17.py 192.168.20.158 --set-volume 50

# Show all device settings
python fiio_k17.py 192.168.20.158 --info

# Monitor volume knob changes
python fiio_k17.py 192.168.20.158 --monitor
```

### Library Usage

```python
from fiio_k17 import FiiOK17

k17 = FiiOK17("192.168.20.158")
settings = k17.connect()
print(f"Current volume: {settings['currentVolume']}")

k17.set_volume(50)

# Background listener for knob changes
k17.on_volume_change = lambda vol: print(f"Volume: {vol}")
k17.listen(blocking=False)
```

### Implementation Notes

1. **Message Framing:** Current implementation reads up to 4096 bytes per recv(). This works for simple commands but may need refinement for rapid sequences or fragmented messages.

2. **Timeouts:** Connection timeout is 5s, listen loop uses 1s timeout to allow clean shutdown.

3. **Reconnection:** Not implemented. The library doesn't auto-reconnect if the connection drops.

---

## Home Assistant Integration - Next Steps

### Architecture Recommendation

1. **Integration Type:** Create a custom component (not a simple script)

2. **Platform:** Implement as a `media_player` entity with:
   - `volume_level` attribute (0.0 - 1.0)
   - `set_volume_level()` service
   - `volume_up()` / `volume_down()` services

3. **Connection Management:**
   - Maintain persistent TCP connection
   - Implement reconnection logic with exponential backoff
   - Handle connection drops gracefully

4. **State Updates:**
   - Use asyncio for non-blocking I/O
   - Push updates to HA state machine when volume changes received
   - Consider polling GET_SETTINGS periodically as a fallback

### Suggested File Structure

```
custom_components/
  fiio_k17/
    __init__.py          # Integration setup
    manifest.json        # Integration metadata
    config_flow.py       # UI configuration
    media_player.py      # Media player entity
    coordinator.py       # Data update coordinator
    protocol.py          # Low-level protocol handling (from fiio_k17.py)
    const.py             # Constants
```

### Config Flow

- Discovery: The FiiO app discovers devices via port scanning. Consider implementing mDNS/SSDP check or manual IP entry.
- Required config: IP address only
- Optional: Polling interval, reconnect settings

### Async Considerations

The proof-of-concept uses blocking sockets. For HA, convert to asyncio:

```python
import asyncio

class AsyncFiiOK17:
    async def connect(self):
        self.reader, self.writer = await asyncio.open_connection(self.host, 12100)
        # ... handshake
    
    async def set_volume(self, volume: int):
        self.writer.write(f"0502000c{volume:04x}".encode())
        await self.writer.drain()
        response = await self.reader.read(4096)
        # ...
```

---

## Open Questions / Further Investigation

1. **Minimal Handshake:** Is the full handshake sequence required, or can we just send INIT + GET_SETTINGS?

2. **Keep-Alive:** Does the K17 drop idle connections? If so, what's the timeout and is there a heartbeat command?

3. **Multiple Clients:** Can multiple clients connect simultaneously? Do all receive volume push notifications?

4. **Other Settings:** Can other settings (gaplessPlay, replayGain, etc.) be changed via the protocol? Likely command 0x01 with a payload.

5. **Error Handling:** What happens if you send an invalid volume (&gt;100)? Invalid command?

6. **Message Boundaries:** Are messages newline-terminated, length-prefixed, or something else? Need more captures to confirm framing.

7. **Prefix 0x06 vs 0x05:** Both appear to be request prefixes. What's the difference?

---

## Test Device Information

- **Device:** FiiO K17 DAC/Amp
- **IP Address:** 192.168.20.158
- **Firmware:** Possibly 3.02 (from handshake response)
- **Control App:** FiiO Control (macOS)

---

## Raw Capture Samples

### Volume Set Command (37)
```
Client: 303530323030306330303235  →  ASCII: 0502000c0025
K17:    613530323030304330303235  →  ASCII: a502000C0025
```

### Volume Push (knob turned from 30 to 40)
```
10.63s: a502000C001F  →  Volume 31
11.29s: a502000C0020  →  Volume 32
11.94s: a502000C0021  →  Volume 33
12.55s: a502000C0022  →  Volume 34
13.28s: a502000C0023  →  Volume 35
13.95s: a502000C0024  →  Volume 36
14.59s: a502000C0025  →  Volume 37
15.25s: a502000C0026  →  Volume 38
15.91s: a502000C0027  →  Volume 39
16.58s: a502000C0028  →  Volume 40
```

---

## Files Produced

1. `fiio_k17.py` - Python proof-of-concept library with CLI
2. `FIIO_K17_PROTOCOL.md` - This documentation file

---

*Document created: January 2025*
*Protocol reverse-engineered from FiiO Control app traffic captures*
