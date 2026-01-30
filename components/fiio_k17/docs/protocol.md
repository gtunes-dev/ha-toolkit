# FiiO K17 Protocol Reverse Engineering

## Overview

This document describes the TCP protocol used by the FiiO K17 DAC/Amp for network control. The protocol was reverse-engineered by capturing traffic between the official FiiO Control macOS app and the K17 device.

---

## Protocol Summary

| Property | Value |
|----------|-------|
| **Transport** | TCP |
| **Port** | 12100 |
| **Encoding** | ASCII-encoded hexadecimal |
| **Connection** | Persistent (device pushes updates) |
| **Clients** | Single client only (second connection gets no responses) |

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

## Important: Unsolicited Notifications

The K17 can send unsolicited `a60a000C000C` notifications at any time, including **between sending a command and receiving its response**. Client implementations must handle this by:

1. Reading multiple messages until the expected response type is received, or
2. Using a single reader task that routes messages to the appropriate handler

This notification appears to be a "sync" or "ready" signal but its exact purpose is unknown.

---

## Connection & Handshake

### Minimal Handshake (Recommended)

For volume control, only two commands are needed:

```
Client → K17: 0599000c0000     (INIT)
K17 → Client: a599000C0302     (ACK, possibly firmware 3.02)

Client → K17: 05010008         (GET_SETTINGS)
K17 → Client: a501009C{...}    (JSON settings)
```

### Full Handshake (FiiO App)

The official app sends additional commands for playlist/track features:

```
Client → K17: 0607000c0000
K17 → Client: a607000C00XX       (XX = input mode, see below)

Client → K17: 062700100000A0A9
K17 → Client: a62700AC... (playlist data)

Client → K17: 0639000c0000
K17 → Client: a639000C00FF

Client → K17: 0628001000000YYY
K17 → Client: a62801C2... (track/volume table info)
```

These are not required for volume control.

### Input Mode (Command 0607)

The `0607` command returns the current input mode:

| Response | Mode |
|----------|------|
| `a607000C0001` | USB |
| `a607000C0007` | Streaming |

The volume control protocol (`0502`) works identically in both modes.

---

## Volume Control

### Set Volume

**Command:** `0502000c00XX`

| Byte(s) | Value | Meaning |
|---------|-------|---------|
| 0 | `05` | Request prefix |
| 1 | `02` | Command: Set Volume |
| 2-3 | `00 0c` | Fixed (flags + length?) |
| 4-5 | `00 XX` | Volume as 16-bit big-endian (0-100) |

**Examples:**
- Volume 37: `0502000c0025` (0x25 = 37)
- Volume 100: `0502000c0064` (0x64 = 100)

**Response:** `a502000C00XX`
- Echoes the volume value back
- Note: An `a60a` notification may arrive before this response

### Volume Push Notifications

When the physical volume knob is turned, the K17 pushes:

```
K17 → Client: a502000C00XX
```

Updates are sent approximately every 600-700ms (one per volume step).

---

## Settings

### GET_SETTINGS Response

```json
{
    "currentVolume": 30,
    "maxVolume": 100,
    "folderJump": true,
    "gaplessPlay": true,
    "memoryPlay": false,
    "memoryType": 0,
    "playMode": 0,
    "replayGain": 0,
    "usbAudio": 2
}
```

The response format is `a501009C{json}` where `9C` (156) is the JSON length.

---

## Commands Reference

| Cmd | Prefix | Name | Request | Response |
|-----|--------|------|---------|----------|
| `99` | `05`/`a5` | INIT | `0599000c0000` | `a599000C0302` |
| `01` | `05`/`a5` | GET_SETTINGS | `05010008` | `a501009C{json}` |
| `02` | `05`/`a5` | SET_VOLUME | `0502000c00XX` | `a502000C00XX` |
| `02` | `a5` | VOLUME_PUSH | N/A (unsolicited) | `a502000C00XX` |
| `0a` | `a6` | NOTIFY | N/A (unsolicited) | `a60a000C000C` |
| `07` | `06`/`a6` | GET_INPUT_MODE | `0607000c0000` | `a607000C00XX` (01=USB, 07=Streaming) |
| `27` | `06`/`a6` | GET_PLAYLIST? | `062700100000A0A9` | `a62700AC...` |
| `39` | `06`/`a6` | UNKNOWN | `0639000c0000` | `a639000C00FF` |
| `28` | `06`/`a6` | GET_TRACK_INFO? | `062800100000001E` | `a62801C2...` |

---

## Implementation Notes

### Single Client Limitation

Only one TCP client can actively communicate with the K17 at a time. A second connection will be accepted but receives no responses to commands. Close the FiiO Control app before connecting with custom software.

### Async Client Architecture

The recommended pattern for handling interleaved messages:

1. **Single reader task** continuously reads from the socket
2. **Commands** set up a Future/callback for their expected response
3. **Reader routes messages**: if a command is waiting, deliver to it; otherwise handle as push notification

This avoids race conditions from concurrent socket reads.

### Message Framing

Messages appear to be complete per TCP read (no explicit framing). The implementation reads up to 4096 bytes per recv() which is sufficient for all known message types.

---

## Connection Management

### Connection Stability

The K17 connection can be dropped by:
- Switching input modes on the device (USB ↔ Streaming)
- Device reboot/power cycle
- Network interruptions
- Idle timeout (duration unknown, but observed in practice)

### Recommended Client Implementation

For robust operation, clients should implement:

1. **Health check**: Periodically send `GET_SETTINGS` (every 30-60 seconds) to verify the connection is alive and keep settings in sync.

2. **Automatic reconnection**: On connection loss, attempt to reconnect with exponential backoff (e.g., 5s → 10s → 20s → 30s max).

3. **Graceful degradation**: Track connection state and surface it to users (e.g., "unavailable" status in Home Assistant).

### No Explicit Keep-Alive Protocol

The device does not appear to require or respond to explicit keep-alive messages. The `a60a000C000C` notifications sent by the device could theoretically serve as implicit keep-alives, but their timing is unpredictable.

---

## Open Questions

1. **Settings Changes:** Can settings (gaplessPlay, etc.) be modified via protocol?
2. **Error Handling:** Response format for invalid commands is unknown.
3. **Idle Timeout:** Exact duration before device drops idle connections is unknown.
4. **Prefix 0x06 vs 0x05:** Both are request prefixes; semantic difference unknown (possibly streaming vs USB-related).

---

## Test Device

- **Device:** FiiO K17 DAC/Amp
- **Firmware:** 3.02 (inferred from handshake)
- **Control App:** FiiO Control (macOS)
- **Tested Modes:** USB and Streaming (volume control verified in both)

---

*Protocol reverse-engineered January 2025*
