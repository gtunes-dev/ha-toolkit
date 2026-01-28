#!/usr/bin/env python3
"""Command-line interface for FiiO K17 control."""

import argparse
import sys
from pathlib import Path

# Add parent directory to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

from fiio_k17 import FiiOK17


def main():
    parser = argparse.ArgumentParser(description="Control FiiO K17 DAC/Amp")
    parser.add_argument("host", help="IP address of the K17")
    parser.add_argument("--get-volume", action="store_true", help="Get current volume")
    parser.add_argument("--set-volume", type=int, metavar="N", help="Set volume (0-100)")
    parser.add_argument("--monitor", action="store_true", help="Monitor volume changes")
    parser.add_argument("--info", action="store_true", help="Show device settings")

    args = parser.parse_args()

    k17 = FiiOK17(args.host)

    try:
        print(f"Connecting to {args.host}...")
        settings = k17.connect()
        print(f"Connected! Current volume: {settings.get('currentVolume')}")

        if args.info:
            print("\nDevice settings:")
            for key, value in settings.items():
                print(f"  {key}: {value}")

        if args.get_volume:
            vol = k17.get_volume()
            print(f"Volume: {vol}")

        if args.set_volume is not None:
            print(f"Setting volume to {args.set_volume}...")
            if k17.set_volume(args.set_volume):
                print("OK")
            else:
                print("Failed")

        if args.monitor:
            print("\nMonitoring volume changes (Ctrl+C to stop)...")
            k17.on_volume_change = lambda v: print(f"Volume: {v}")
            try:
                k17.listen(blocking=True)
            except KeyboardInterrupt:
                print("\nStopped")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        k17.disconnect()


if __name__ == "__main__":
    main()
