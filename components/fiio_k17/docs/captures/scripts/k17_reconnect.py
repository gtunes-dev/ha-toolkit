#!/usr/bin/env python3
"""Measure how long the K17 refuses connections after a client disconnects.

Usage: python3 k17_reconnect.py <host> [--cycles N]

Each cycle: connect, GET_SETTINGS, read reply, close; then retry connect every 0.25s
and report how long until the device accepts again.
"""

import argparse
import socket
import time

PORT = 12100


def wait_for_accept(host: str, limit: float = 120.0) -> tuple[float, int, socket.socket | None]:
    start = time.monotonic()
    attempts = 0
    while time.monotonic() - start < limit:
        attempts += 1
        try:
            s = socket.create_connection((host, PORT), timeout=3)
            return time.monotonic() - start, attempts, s
        except ConnectionRefusedError:
            time.sleep(0.25)
        except OSError as err:
            print(f"  other error: {err}")
            time.sleep(0.25)
    return time.monotonic() - start, attempts, None


def query(s: socket.socket) -> str:
    s.sendall(b"05010008")
    s.settimeout(1.0)
    buf = b""
    end = time.monotonic() + 1.0
    while time.monotonic() < end:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            return buf.decode("ascii", "replace") + "<EOF>"
        buf += chunk
        if b"}" in buf:
            break
    return buf.decode("ascii", "replace")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("--cycles", type=int, default=3)
    args = p.parse_args()

    print("initial connect (may be refused if a previous socket just closed)")
    waited, attempts, s = wait_for_accept(args.host)
    print(f"  accepted after {waited:.2f}s ({attempts} attempts)")
    for cycle in range(1, args.cycles + 1):
        if s is None:
            print("  gave up")
            return
        reply = query(s)
        print(f"cycle {cycle}: reply {len(reply)} chars: {reply[:40]!r}")
        s.close()
        waited, attempts, s = wait_for_accept(args.host)
        print(f"  reconnect accepted after {waited:.2f}s ({attempts} attempts)")
    if s:
        s.close()


if __name__ == "__main__":
    main()
