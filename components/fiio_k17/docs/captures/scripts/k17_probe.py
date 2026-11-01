#!/usr/bin/env python3
"""Raw-frame probe for the FiiO K17. Prints every byte the device sends, with timing.

Usage: python3 k17_probe.py <host> [--listen SECONDS]

Sequence (each step on the same socket, unless noted):
  0. Fresh socket, GET_SETTINGS with no handshake (is 0599 required?)
  1. INIT handshake (0599)
  2. GET_SETTINGS (0501)
  3. GET_INPUT (0607)
  4. SET_VOLUME to the *current* volume (no audible change) to see the ack sequence
  5. Passive listen: turn the knob / switch inputs on the device during this window
"""

import argparse
import json
import re
import socket
import time

PORT = 12100
T0 = time.monotonic()


def ts() -> str:
    return f"{time.monotonic() - T0:7.3f}s"


def drain(sock: socket.socket, seconds: float) -> str:
    """Read everything that arrives within `seconds`, printing each recv() chunk."""
    sock.settimeout(0.1)
    end = time.monotonic() + seconds
    buf = ""
    while time.monotonic() < end:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            print(f"  [{ts()}] <EOF: device closed connection>")
            break
        text = chunk.decode("ascii", errors="replace")
        print(f"  [{ts()}] recv {len(chunk):4d} bytes: {text!r}")
        buf += text
    return buf


def split_frames(buf: str) -> None:
    """Split by the length field at chars 4-8 (hypothesis) and report whether it holds."""
    i = 0
    while i < len(buf):
        hdr = buf[i : i + 8]
        try:
            length = int(hdr[4:8], 16)
        except ValueError:
            print(f"    !! unparseable header at offset {i}: {buf[i:i+16]!r}")
            return
        frame = buf[i : i + length]
        ok = len(frame) == length and length >= 8
        print(f"    frame {hdr[:4]} len={length:4d} {'OK ' if ok else 'BAD'} {frame[:60]!r}{'...' if len(frame) > 60 else ''}")
        if "{" in frame:
            try:
                data = json.loads(frame[frame.index("{") :])
                print(f"    json ({len(data)} keys): {json.dumps(data, sort_keys=True)}")
            except json.JSONDecodeError as err:
                print(f"    !! json decode failed: {err}")
        if not ok:
            return
        i += length


def step(sock: socket.socket, label: str, cmd: str, wait: float = 1.5) -> str:
    print(f"\n== {label}: send {cmd!r}")
    sock.sendall(cmd.encode("ascii"))
    buf = drain(sock, wait)
    split_frames(buf)
    return buf


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("--listen", type=float, default=20.0)
    args = p.parse_args()

    print(f"== 0: fresh socket, no handshake")
    with socket.create_connection((args.host, PORT), timeout=3) as s:
        step(s, "0 GET_SETTINGS (no INIT)", "05010008")
    time.sleep(4.0)  # device refuses connections for ~2-3s after a close

    with socket.create_connection((args.host, PORT), timeout=3) as s:
        print(f"\n[{ts()}] connected; unsolicited data on connect:")
        drain(s, 1.0)
        step(s, "1 INIT", "0599000c0000")
        settings = step(s, "2 GET_SETTINGS", "05010008")
        step(s, "3 GET_INPUT", "0607000c0000")

        m = re.search(r'"currentVolume"\s*:\s*(\d+)', settings)
        if m:
            vol = int(m.group(1))
            step(s, f"4 SET_VOLUME (re-set current={vol})", f"0502000c{vol:04x}", wait=2.0)
        else:
            print("\n== 4 skipped: couldn't read current volume")

        print(f"\n== 5 listening {args.listen:.0f}s: turn the knob, switch inputs on the device")
        split_frames(drain(s, args.listen))


if __name__ == "__main__":
    main()
