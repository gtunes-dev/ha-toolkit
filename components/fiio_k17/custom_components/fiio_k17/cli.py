#!/usr/bin/env python3
"""Command-line interface for FiiO K17 control."""

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running directly or as a module
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from client import FiiOK17Client
else:
    from .client import FiiOK17Client


async def main_async(args):
    """Async main function."""
    client = FiiOK17Client(args.host)

    try:
        print(f"Connecting to {args.host}...")
        settings = await client.connect()
        print(f"Connected! Current volume: {settings.get('currentVolume')}")

        if args.info:
            print("\nDevice settings:")
            for key, value in settings.items():
                print(f"  {key}: {value}")

        if args.get_volume:
            settings = await client.get_settings()
            print(f"Volume: {settings.get('currentVolume')}")

        if args.set_volume is not None:
            print(f"Setting volume to {args.set_volume}...")
            if await client.set_volume(args.set_volume):
                print("OK")
            else:
                print("Failed")

        if args.monitor:
            print("\nMonitoring volume changes (Ctrl+C to stop)...")
            client.on_volume_change = lambda v: print(f"Volume: {v}")
            try:
                # Keep running until interrupted
                while client.connected:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nStopped")

    except ConnectionError as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        await client.disconnect()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Control FiiO K17 DAC/Amp")
    parser.add_argument("host", help="IP address of the K17")
    parser.add_argument("--get-volume", action="store_true", help="Get current volume")
    parser.add_argument("--set-volume", type=int, metavar="N", help="Set volume (0-100)")
    parser.add_argument("--monitor", action="store_true", help="Monitor volume changes")
    parser.add_argument("--info", action="store_true", help="Show device settings")

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
