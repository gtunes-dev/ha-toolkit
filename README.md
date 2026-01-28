# FiiO K17 Control

A Python library and Home Assistant integration for controlling the FiiO K17 DAC/Amp over your local network.

## Features

- Get and set volume (0-100)
- Monitor real-time volume changes (when the physical knob is turned)
- Retrieve device settings
- Home Assistant integration (coming soon)

## Requirements

- Python 3.9+
- FiiO K17 connected to your local network
- Device IP address (check your router or the FiiO Control app)

## Installation

```bash
git clone https://github.com/yourusername/fiio-k17-control.git
cd fiio-k17-control
```

## Usage

### Command Line

```bash
# Show device info and settings
python examples/cli.py 192.168.1.100 --info

# Get current volume
python examples/cli.py 192.168.1.100 --get-volume

# Set volume to 50
python examples/cli.py 192.168.1.100 --set-volume 50

# Monitor volume knob changes in real-time
python examples/cli.py 192.168.1.100 --monitor
```

### As a Library

```python
from fiio_k17 import FiiOK17

k17 = FiiOK17("192.168.1.100")
k17.connect()

# Get current settings
settings = k17.get_settings()
print(f"Current volume: {settings['currentVolume']}")

# Set volume
k17.set_volume(50)

# Listen for volume knob changes
k17.on_volume_change = lambda vol: print(f"Volume changed to: {vol}")
k17.listen(blocking=False)  # Background thread

# When done
k17.disconnect()
```

## Protocol Documentation

See [docs/protocol.md](docs/protocol.md) for details on the reverse-engineered TCP protocol.

## Limitations

- Only one client can connect to the K17 at a time (close the FiiO Control app first)
- This library uses the reverse-engineered protocol - it may break with firmware updates

## License

MIT License - see [LICENSE](LICENSE) for details.
