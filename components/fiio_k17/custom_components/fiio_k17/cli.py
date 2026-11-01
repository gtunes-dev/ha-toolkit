#!/usr/bin/env python3
"""Command-line interface for FiiO K17 control."""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow running directly or as a module
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    from client import INPUTS, FiiOK17Client, FiiOK17Error
else:
    from .client import INPUTS, FiiOK17Client, FiiOK17Error


def resolve_input(value: str) -> str:
    """Accept an input code (e.g. 0003) or name (e.g. coaxial)."""
    if value in INPUTS:
        return value
    for code, name in INPUTS.items():
        if name.lower() == value.lower():
            return code
    raise SystemExit(f"Unknown input {value!r}; choose from: {', '.join(INPUTS.values())}")


async def main_async(args):
    """Async main function."""
    client = FiiOK17Client(args.host)

    try:
        state = await client.refresh()
        print(f"Volume: {state.volume}  Input: {state.input_name}")

        if args.info:
            print("\nDevice settings:")
            for key, value in state.settings.items():
                print(f"  {key}: {value}")

        if args.set_volume is not None:
            state = await client.set_volume(args.set_volume)
            print(f"Volume set: {state.volume}")

        if args.step is not None:
            state = await client.step_volume(args.step)
            print(f"Volume stepped: {state.volume}")

        if args.set_input is not None:
            state = await client.set_input(resolve_input(args.set_input))
            print(f"Input set: {state.input_name}")

        if args.monitor:
            print(f"\nMonitoring for {args.monitor:.0f}s (Ctrl+C to stop)...")
            client.on_update = lambda s: print(f"Volume: {s.volume}  Input: {s.input_name}")
            await client.refresh(hold=args.monitor)
            try:
                await asyncio.sleep(args.monitor)
            except asyncio.CancelledError:
                pass

    except FiiOK17Error as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        await client.close()


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Control FiiO K17 DAC/Amp")
    parser.add_argument("host", help="IP address of the K17")
    parser.add_argument("--set-volume", type=int, metavar="N", help="Set volume (0-100)")
    parser.add_argument("--step", type=int, metavar="N", help="Change volume by N (e.g. 2 or -2)")
    parser.add_argument("--set-input", metavar="INPUT", help="Switch input (name or code)")
    parser.add_argument("--monitor", type=float, metavar="SECONDS", help="Print pushed changes")
    parser.add_argument("--info", action="store_true", help="Show device settings")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="%(asctime)s.%(msecs)03d %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nStopped")


if __name__ == "__main__":
    main()
