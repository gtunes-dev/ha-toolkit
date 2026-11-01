#!/usr/bin/env python3
"""Sweep reconnect delays after a clean close and record the outcome of each.

Usage: python3 k17_sweep.py <host> [--delays 0,0.5,1,...] [--close fin|rst]

For each delay: get a known-good session, query, close, sleep <delay>, then make ONE
connect+query attempt and classify: ok / refused / reset / eof / timeout.
"""

import argparse
import socket
import struct
import time

PORT = 12100


def query(s: socket.socket, timeout: float = 2.0) -> str:
    """Send GET_SETTINGS and read until the settings frame plus any trailing a60a arrive."""
    s.sendall(b"05010008")
    s.settimeout(0.3)
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            if b"}" in buf:
                break
            continue
        if not chunk:
            raise EOFError(buf.decode("ascii", "replace"))
        buf += chunk
    if b"}" not in buf:
        raise TimeoutError(buf.decode("ascii", "replace"))
    return buf.decode("ascii", "replace")


def close(s: socket.socket, mode: str) -> str:
    if mode == "rst":
        s.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        s.close()
        return "rst sent"
    s.shutdown(socket.SHUT_WR)
    s.settimeout(2.0)
    t = time.monotonic()
    try:
        while s.recv(4096):
            pass
        note = f"device EOF after {time.monotonic() - t:.2f}s"
    except socket.timeout:
        note = "no device EOF within 2s"
    except OSError as err:
        note = f"close err {err}"
    s.close()
    return note


def attempt(host: str) -> tuple[str, socket.socket | None]:
    try:
        s = socket.create_connection((host, PORT), timeout=3)
    except ConnectionRefusedError:
        return "refused", None
    except OSError as err:
        return f"connect-err {err}", None
    try:
        reply = query(s)
        return f"ok ({len(reply)} chars)", s
    except ConnectionResetError:
        s.close()
        return "reset", None
    except EOFError as e:
        s.close()
        return f"eof (got {str(e)[:30]!r})", None
    except TimeoutError as e:
        s.close()
        return f"timeout (got {str(e)[:30]!r})", None


def get_good(host: str, limit: float = 120) -> socket.socket:
    start = time.monotonic()
    tries = 0
    while time.monotonic() - start < limit:
        tries += 1
        outcome, s = attempt(host)
        if s:
            if tries > 1:
                print(f"    (recovered after {time.monotonic() - start:.1f}s, {tries} tries)")
            return s
        time.sleep(0.5)
    raise SystemExit("device never recovered")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("--delays", default="0,0.5,1,2,3,5,8,12")
    p.add_argument("--close", choices=["fin", "rst"], default="fin")
    args = p.parse_args()

    for d in [float(x) for x in args.delays.split(",")]:
        s = get_good(args.host)
        note = close(s, args.close)
        time.sleep(d)
        outcome, s2 = attempt(args.host)
        print(f"delay {d:5.1f}s  [{note}]  -> {outcome}")
        if s2:
            close(s2, args.close)
        time.sleep(0.5)


if __name__ == "__main__":
    main()
