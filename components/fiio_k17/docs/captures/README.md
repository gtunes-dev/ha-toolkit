# K17 Raw Captures

Raw TCP captures from a FiiO K17 on port 12100. They back up the claims in [../protocol.md](../protocol.md). All captures were taken on 2026-11-01, on the same device, before and after a firmware update. The Home Assistant integration was disabled and the FiiO Control app was closed, except in test 07.

| Folder | Firmware | How to tell |
|---|---|---|
| `old-firmware/` | Version before the update; it doesn't report a version number | Settings frame is 156 chars (`a501009C`), 9 JSON keys |
| `new-firmware/` | `soc_version: 265` in the settings JSON | Settings frame is 388 chars (`a5010184`), 22 JSON keys |

Both firmwares answer the `0599` handshake with `a599000C0302`, so `0302` is not the firmware version.

## Tests

| # | File | What it does | Script |
|---|---|---|---|
| 01 | `01-probe.txt` | Sends `05010008` on a fresh socket with no handshake. Then, on a second socket: `0599` handshake, `05010008`, `0607` input query, and `0502` set volume to the current value. Prints every `recv()` and splits frames by the length field. | `k17_probe.py` |
| 02 | `02-reconnect-sweep-clean-close*.txt` | Queries, closes cleanly (half-close, then waits for the device's EOF), sleeps for the delay shown, then makes one connect+query attempt. | `k17_sweep.py` |
| 03 | `03-reconnect-*.txt` | The same test, but closing abruptly with a TCP reset. On the old firmware the unclean close came from `k17_reconnect.py` closing while unread data was pending. | `k17_sweep.py --close rst`, `k17_reconnect.py` |
| 04 | `04-push-inputs-partial.txt` | Passive listen while inputs were changed on the device. Partial cycle. | `k17_listen.py` |
| 05 | `05-push-inputs-full-cycle.txt` | Passive listen while inputs were cycled Optical → Coaxial → Line In → Balanced → Bluetooth → Streaming → Local Play → USB → Optical. | `k17_listen.py --seconds 60` |
| 06 | `06-push-volume-knob.txt` | Knob turned for 30 s. The first 15 s are passive; `05010008` is sent at 15 s. | Inline variant of `k17_listen.py` |
| 07 | `07-second-client-while-app-connected.txt` | The FiiO Control app holds the device. A second client connects, sends `05010008` at 1 s, and waits up to 10 s. The app kept working in both runs. | Inline |
| 08 | `new-firmware/08-set-input.txt` | `0607` query, `0657000c0001` (Optical → USB), `0607` query. | Inline |
| 09 | `new-firmware/09-set-input-back-to-back.txt` | Two switches 1 s apart (the second is ignored), then a switch to the current input (no reply), then a switch 3 s later (works). | Inline |
| 10 | `new-firmware/10-set-input-lockout-sweep.txt` | Pairs of switches with a 2, 3, 4 and 6 s gap, to measure the lockout between switches. | Inline |

Tests 08–10 were only run on the new firmware.

In the old-firmware Streaming capture (05), Roon was playing a track, so the device pushed now-playing metadata. In the new-firmware capture it was not playing.

## Running the scripts

```bash
python3 scripts/k17_probe.py <host> [--listen SECONDS]
python3 scripts/k17_sweep.py <host> [--delays 0,0.5,1] [--close fin|rst]
python3 scripts/k17_listen.py <host> [--seconds N] [--init]
python3 scripts/k17_reconnect.py <host> [--cycles N]
```

Disable the integration and close the FiiO app first; the device only serves one client. Leave about 3 s between runs, because the device refuses connections briefly after a close.
