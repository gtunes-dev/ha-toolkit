#!/usr/bin/env python3
"""Connect and passively print every frame the K17 pushes, with timing.

Usage: python3 k17_listen.py <host> [--seconds N] [--init]
"""

import argparse
import socket
import time

PORT = 12100


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("host")
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--init", action="store_true", help="send 05010008 first")
    args = p.parse_args()

    s = socket.create_connection((args.host, PORT), timeout=3)
    t0 = time.monotonic()
    print(f"connected; listening {args.seconds:.0f}s — GO", flush=True)
    if args.init:
        s.sendall(b"05010008")
    s.settimeout(0.2)
    buf = ""
    while time.monotonic() - t0 < args.seconds:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            continue
        if not chunk:
            print(f"[{time.monotonic() - t0:7.3f}s] <EOF>")
            break
        text = chunk.decode("ascii", errors="replace")
        print(f"[{time.monotonic() - t0:7.3f}s] recv {len(chunk):4d}: {text!r}", flush=True)
        buf += text
        # Peel off complete frames using the length field
        while len(buf) >= 8:
            try:
                n = int(buf[4:8], 16)
            except ValueError:
                print(f"    !! bad header {buf[:16]!r}")
                buf = ""
                break
            if len(buf) < n:
                break
            print(f"    frame {buf[:n][:70]!r}")
            buf = buf[n:]
    s.shutdown(socket.SHUT_WR)
    s.close()
    print("done")


if __name__ == "__main__":
    main()
