# FiiO K17 Protocol Reverse Engineering

## Overview

This document describes the TCP protocol the FiiO K17 DAC/Amp uses for network control. FiiO does not publish it.

Sources:

1. **FiiO Control app capture (January 2025).** Traffic between the official macOS app and the K17.
2. **Live probing (2026-11-01).** Raw-frame tests run directly against a K17, before and after a firmware update. The captures and scripts are in [captures/](captures/).
3. **[benedictjohannes/fiio-direct-remote](https://github.com/benedictjohannes/fiio-direct-remote).** Another reverse-engineering effort. We used it for the input-switch command, input codes and discovery details. Where its claims disagree with our captures, this doc explains why.

Each claim carries a status:

- **Verified:** confirmed in our captures on both firmwares unless noted.
- **Observed:** seen in our captures but not understood.
- **Unverified:** from another source; not yet tested by us.

### Firmware versions tested

| Label | Identification | Settings frame |
|---|---|---|
| Old | No version field reported | 156 chars, 9 JSON keys |
| New | `"soc_version": 265` in the settings JSON | 388 chars, 22 JSON keys |

Both firmwares answer the handshake with `a599000C0302`, so `0302` is a protocol revision, not the firmware version.

---

## Protocol Summary

| Property | Value |
|----------|-------|
| **Transport** | TCP, port 12100 |
| **Encoding** | ASCII text. Frame headers are hex digits; some frames carry a JSON body |
| **Framing** | Length field in the header (see [Frame Format](#frame-format)) |
| **Clients** | One active client. Others are accepted but get no replies |
| **Handshake** | Optional |
| **Push updates** | Sent to the connected client with no subscription needed |

---

## Frame Format

**Verified.** Every frame starts with an 8-character header:

```
chars 0-1   prefix   (subsystem / direction)
chars 2-3   command
chars 4-7   total frame length in characters, including this header (hex)
chars 8-    payload  (hex digits or JSON), length - 8 characters
```

Examples:

| Frame | Length field | Frame length |
|---|---|---|
| `05010008` | `0008` | 8 (header only) |
| `0502000c0025` | `000c` | 12 |
| `062700100000A0A9` | `0010` | 16 |
| `a2020013{"state":2}` | `0013` | 19 |
| `a501009C{...}` | `009C` | 156 |
| `a5010184{...}` | `0184` | 388 |
| `a20201F9{...}` | `01F9` | 505 |

The device writes hex digits in uppercase. It accepts lowercase in requests: all our requests used lowercase. fiio-direct-remote sends uppercase volume values and reports that they work.

### Reading frames

**Do not assume one frame per `recv()`.** The device often sends related frames back to back. For example, the settings reply is followed immediately by `a60a000C000C`, and a client may receive them in one read or in two. Large frames can also be split across reads.

Read the 8-character header, parse the length, then read exactly `length - 8` more characters.

Do not find the end of a JSON frame by looking for `}`. The now-playing frame (`a202`) holds JSON nested inside a string, so `}` appears in the middle of it.

### Prefixes

| Prefix | Seen as | Notes |
|---|---|---|
| `05` | Request | Settings, volume, handshake ("SoC" subsystem in fiio-direct-remote's terms) |
| `a5` | Response / push | Replies to `05` requests; volume pushes |
| `06` | Request | Input query/switch and the FiiO app's extra commands ("MCU" subsystem) |
| `a6` | Response / push | Replies to `06` requests; input pushes; `a60a` |
| `a1` | Push | Playback-related (**observed**) |
| `a2` | Push | Now-playing JSON (**observed**) |
| `aa` | Push | Seen once when switching to Streaming (**observed**) |

Responses appear to set the high nibble of the request prefix to `a` (`05` → `a5`, `06` → `a6`).

---

## Connection Behavior

### Single client

**Verified.** Only one client is served at a time. When the FiiO Control app is connected, a second client's TCP connection is accepted, but its requests get no reply:

| Firmware | Second client's experience |
|---|---|
| Old | Accepted, no replies, the connection is never closed by the device |
| New | Accepted, no replies, the device resets the connection about 6.5 s after it connected |

In both cases the FiiO app kept working normally. A client that gets no reply within a couple of seconds should treat the device as **busy**, not offline, and close its connection.

### Reconnect cooldown after a close

**Verified.** After a client disconnects, the device refuses new connections for a short time. It refuses with a TCP connection-refused error, or it accepts the connection and then resets it.

| Firmware | After a clean close | After an abrupt close (TCP reset) |
|---|---|---|
| Old | Refused for about 2–3 s | Accepted, then reset on the first request |
| New | Usually about 0.1 s; one refusal at 0.4 s | Refused or reset for about 1–2 s |

A clean close means: read everything the device has sent, half-close (`shutdown(SHUT_WR)`), then wait for the device's EOF. The device sends its EOF within about 10 ms. Clients should always close cleanly, and should retry a refused connection for a few seconds before reporting failure.

### Handshake is optional

**Verified.** A fresh connection can send `05010008` straight away and get a full settings reply. Volume and input pushes also arrive on a connection that has sent nothing at all.

### Input switching does not drop the connection

**Verified.** A passive connection stayed up while the device cycled through all eight inputs, on both firmwares.

The previous version of this doc said that switching between USB and Streaming drops the connection. We could not reproduce that. That observation came from a client that had sent the handshake. The drops may have had a different cause, such as the idle drop below.

### Idle drops

**Unverified.** The January 2025 notes recorded the device occasionally dropping idle connections. The timeout was never measured, and we have not tested it. A client that releases the connection when idle avoids the question.

---

## Commands

### Handshake: `0599000c0000`

**Verified.** Optional.

```
→ 0599000c0000
← a599000C0302
```

### Get settings: `05010008`

**Verified.** The reply is a settings frame followed immediately by `a60a000C000C`.

```
→ 05010008
← a5010184{...json...}
← a60a000C000C
```

`a60a000C000C` is **always the second half of this reply**. Earlier notes called it an unpredictable notification, because it was being read as a separate message after the settings reply, often as the reply to the next command.

Old firmware JSON (156-char frame):

```json
{"currentVolume":13,"folderJump":true,"gaplessPlay":true,"maxVolume":100,"memoryPlay":false,"memoryType":0,"playMode":0,"replayGain":0,"usbAudio":2}
```

New firmware JSON (388-char frame):

```json
{"currentVolume":19,"folderJump":false,"gaplessPlay":false,"maxVolume":100,"memoryPlay":false,"memoryType":0,"playMode":0,"muteMode":0,"replayGain":0,"usbAudio":2,"artist_sub_album":1,"http_replace_link":0,"soc_version":265,"ota_site":"k17pack.fiio.net","width":240,"height":240,"quality":100,"rgb":888,"cus_count":0,"sys_count":0,"video":"[\"mp4\"]","image":"[\"png\", \"gif\"]"}
```

Notes:

- `usbAudio` stayed `2` on every input. It does **not** indicate the current input; use `0607` for that. fiio-direct-remote reports the same.
- `muteMode` is new. We don't know of a mute command yet.

### Set volume: `0502000cVVVV`

**Verified.** `VVVV` is the volume, 0–100, as 4 hex digits.

```
→ 0502000c000d        (volume 13)
← a502000C000D
```

The device echoes the new volume and sends nothing else. The `a60a` that earlier notes saw "before the volume reply" was left over from an earlier settings request.

### Get input: `0607000c0000`

**Verified.** The reply is the input code directly; see [Input Codes](#input-codes).

```
→ 0607000c0000
← a607000C0001        (USB)
```

fiio-direct-remote says this command returns `a60a000C000C` first. We did not see that on either firmware.

### Set input: `0657000cMMMM`

**Verified** on the new firmware. `MMMM` is an input code. The command came from fiio-direct-remote.

```
→ 0657000c0001        (switch to USB)
← a607000C0001        (~20 ms later)
```

We saw no `a60a` with it, though fiio-direct-remote says one may come first. Two cases get **no reply at all**:

- **Switching to the input that is already selected.** Nothing changes, and nothing is sent back.
- **Switching within about 2–3 s of the previous switch.** The device silently ignores the command. In our tests a 2 s gap was ignored, and gaps of 3 s or more worked. The previous switch counts whether it was made over the network or on the device. Anything a client tracks only covers its own switches and the pushes it received while connected.

A client should not take a missing reply to `0657` as "busy". It should query `0607` instead:

- If the query also gets no reply, the device is busy.
- If the query shows the old input, the switch was ignored. Wait out the lockout and retry.

See captures 08–10.

### FiiO app extras

**Unverified.** Seen in the January 2025 capture of the FiiO app. None of these are needed for volume or input control.

| Request | Reply | Notes |
|---|---|---|
| `062700100000A0A9` | `a62700AC...` | Playlist data? fiio-direct-remote guesses EQ |
| `0639000c0000` | `a639000C00FF` | Unknown |
| `062800100000001E` | `a62801C2...` | Track info? fiio-direct-remote guesses EQ |

---

## Push Messages

The device sends these to the connected client without being asked.

| Frame | Trigger | Status |
|---|---|---|
| `a502000CVVVV` | Volume knob, one frame per step; about 300 ms apart when turning quickly | **Verified** |
| `a607000CMMMM` | Input changed on the device | **Verified** |
| `a20201F9{...}` | Switched to Streaming while Roon was playing; now-playing JSON | **Observed** (old firmware) |
| `a103001000020B70` | Same moment as above. Likely playback position in ms (0x20B70 = 134,000 = 2:14) | **Observed** (old firmware) |
| `a2020013{"state":2}` | Switched away from Streaming. Possibly paused/stopped | **Observed** (both) |
| `a102000CXXXX` | Around Streaming / Local Play switches. `0000` on old firmware, `000A` on new | **Observed** (both) |
| `aa05000C0001` | Switched to Streaming (new firmware, nothing playing) | **Observed** (new) |

Now-playing JSON as captured (whitespace inside the nested string is as sent):

```
{"song":"{\"id\":0,\"pos_id\":0,\"song_name\":\"Buckle\",\"song_duration_time\":203000, \"song_file_path\":\"\", \"song_sample_rate\":0,\"song_encoding_rate\":0,\"song_bit_rate\":0, \"song_artist_name\":\"Florence + the Machine\",\"song_album_name\":\"\",\"song_style_name\":\"\", \"song_track\":0,\"song_channel\":0,\"is_sacd\":false,\"is_cue\":false,\"is_dsd\":false}", "love":false,"playerflag":255,"state":1, "playing_num":"","work_mode":"ROON"}
```

`song` is itself a JSON document stored as a string, so it needs a second parse.

---

## Input Codes

**Verified** for pushes and the `0607` query, by cycling every input on the device and recording each push. Codes `0001` and `0002` are also verified with `0657`.

| Code | Input |
|---|---|
| `0001` | USB |
| `0002` | Optical |
| `0003` | Coaxial |
| `0004` | Line In |
| `0005` | Balanced |
| `0006` | Bluetooth |
| `0007` | Streaming |
| `0008` | Local Play (missing from fiio-direct-remote's list) |

---

## Discovery

**Unverified.** From fiio-direct-remote.

- **UDP multicast heartbeat:** the ASCII text `K17` sent to `224.0.0.255`, port 12101, every 2 s, from the device's IP.
- **MAC prefix:** `40:d9:5a` (Ingenic Semiconductor, the chip maker; other Ingenic-based devices share it).
- **mDNS hostname:** `ingenic.local`.

---

## Notes on fiio-direct-remote

Its K17Protocol.md describes a "transient event prefix" on the settings reply: the reply supposedly starts with a different header depending on the last event, such as `a502000C<vol>` after a volume change or `a607000C<mode>` after an input change.

**That is very likely a side effect of how its client reads the socket.** The client sends a command, reads until it has 12 characters (or until a `}` for settings requests), and returns. It never reads anything after that. Any frame still pending, such as a volume echo or a push, stays in the socket and appears at the start of the next reply.

For the same reason, its claim that set volume returns `a60a000C000C` "followed by `a502…` on subsequent status poll" is the `a60a` left over from the previous settings request, followed by the real reply.

---

## Client Implementation Notes

These follow from the verified behavior above.

1. **Read by frame length** and dispatch on prefix + command (`a502`, `a607`, `a501`, ...). Don't treat "the next read" as the reply to the last request.
2. **Release the connection when idle.** Holding it locks out the FiiO app and any other client. Pushes reach whoever is connected, so a client still receives knob and input changes during the time it holds the connection.
3. **Close cleanly** and **retry refused connects for a few seconds** to ride out the post-close cooldown.
4. **No reply means busy**, not offline: another client holds the device. The device itself is unaffected by the attempt. The exception is `0657` (set input); see its section.
5. **Skip the handshake.** It isn't required.

---

## Open Questions

1. **Set input on the old firmware:** `0657` was only tested after the update.
2. **Mute:** the new firmware reports `muteMode`. Is there a mute command, and does muting push a frame?
3. **Playback pushes:** do `a202`/`a103` arrive on track changes and play/pause, or only on input switches? Can they be requested?
4. **Meaning of `a102`, `aa05` and `a60a`'s `000C` payload.**
5. **Idle drop:** does the device ever drop a connection that is left idle, and after how long?
6. **Error replies:** what an invalid command returns is unknown.

---

## Test Device

- **Device:** FiiO K17 DAC/Amp
- **Firmware:** tested before and after the update to `soc_version` 265; see [Firmware versions tested](#firmware-versions-tested)
- **Tools:** FiiO Control (macOS) capture, January 2025; raw socket probes, 2026-11-01 ([captures/](captures/))
