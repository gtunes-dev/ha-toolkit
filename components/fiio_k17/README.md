# FiiO K17 Control

A Home Assistant custom integration for controlling the FiiO K17 DAC/Amp's volume and input over your local network.

I built this integration because I wanted to use my [Philips Hue Tap Dial Switch](https://community.home-assistant.io/t/zha-philips-hue-tap-switch-mini-custom-controls-rdm002/789654) (for which I also wrote a blueprint) to control my K17's volume. Now you can adjust the K17's volume from any Home Assistant automation, dashboard, or physical controller.

**Note:** This integration supports volume and input selection. The K17's network protocol does not support transport controls (play/pause/skip) when using streaming sources like USB or Bluetooth.

> **Sharing the device with the FiiO Control app:** The K17 serves only one network client at a time. This integration connects only briefly: for a few tens of milliseconds every 10 seconds, and for 15 seconds after each command. So the FiiO Control app can usually be used at the same time. While the app is connected, Home Assistant keeps showing the last known volume and input, and commands from Home Assistant fail with an "in use by another app" error.

## Features

- **Volume control** via Home Assistant media player entity
- **Input selection**: USB, Optical, Coaxial, Line In, Balanced, Bluetooth, Streaming, Local Play
- **Updates from the device**: knob turns and input changes show up within about 10 seconds, or immediately within 15 seconds of a Home Assistant command
- **Simple setup** via the Home Assistant UI

## Requirements

- Home Assistant 2025.1 or later
- FiiO K17 connected to your local network (same network as HA)
- The device's IP address

## Installation

1. Download or clone this repository

2. Copy the `custom_components/fiio_k17` folder from this directory to your Home Assistant config directory:
   ```
   <ha-config>/custom_components/fiio_k17/
   ```

3. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **FiiO K17**
4. Enter your device's IP address

The integration will create a media player entity with volume control and input selection.

## Usage

Once configured, you can:

- **Control volume** via the media player card or slider
- **Switch inputs** via the media player's source selector or the `media_player.select_source` service
- **Use in automations** with the `media_player.volume_set` service
- **Monitor volume and input**: the entity follows changes made on the device (see [How updates work](#how-updates-work))

### Example Automation

```yaml
automation:
  - alias: "Set K17 volume for movie time"
    trigger:
      - platform: state
        entity_id: media_player.living_room_tv
        to: "playing"
    action:
      - service: media_player.volume_set
        target:
          entity_id: media_player.fiio_k17
        data:
          volume_level: 0.5
      - service: media_player.select_source
        target:
          entity_id: media_player.fiio_k17
        data:
          source: "Optical"
```

### Advanced: Volume Increment/Decrement

For rotary controllers or buttons that need to adjust volume by a specific step (e.g., +3 or -3), you can read the current volume and apply a delta:

```yaml
# Increase volume by 3
action:
  - variables:
      current: "{{ state_attr('media_player.fiio_k17', 'volume_level') | float(0) }}"
      step: 0.03
  - service: media_player.volume_set
    target:
      entity_id: media_player.fiio_k17
    data:
      volume_level: "{{ [1.0, current + step] | min }}"

# Decrease volume by 3
action:
  - variables:
      current: "{{ state_attr('media_player.fiio_k17', 'volume_level') | float(0) }}"
      step: 0.03
  - service: media_player.volume_set
    target:
      entity_id: media_player.fiio_k17
    data:
      volume_level: "{{ [0.0, current - step] | max }}"
```

This pattern starts from the volume Home Assistant last saw. If someone turned the physical knob in the last few seconds, that value can be up to one poll (10 seconds) old. `media_player.volume_up` and `media_player.volume_down` don't have this problem: they read the device's current volume first when needed, but they only step by 1.

## How updates work

The K17 only serves one client, so the integration doesn't hold a connection open:

- **Polling:** every 10 seconds it connects, reads the volume and input, and disconnects.
- **After a command** (volume, input), it keeps the connection open for 15 seconds. During that time, changes made on the device appear immediately.
- **Another app connected:** the device accepts the connection but doesn't reply. The integration treats that as busy, not offline. It keeps the last known state and tries again at the next poll.
- **Device unreachable:** the entity becomes unavailable after 3 failed polls in a row.

## Troubleshooting

### "Cannot connect" error during setup

1. **Verify the IP address** - Check your router or the FiiO Control app for the correct IP
2. **Check network connectivity** - Ensure HA can reach the device (same VLAN/subnet)

### "Device is in use by another app" error

Close the FiiO Control app (or any other K17 controller) and try again.

### Input change didn't happen

The K17 ignores an input change made within about 3 seconds of the previous one. The integration notices this and retries once after waiting, so a quick second change can take a few seconds to complete.

### Finding your K17's IP address

- Check your router's DHCP client list
- Use the FiiO Control app (Settings → Device Info)
- The device hostname is typically `fiio_k17`

## Limitations

- **Single client** - While another app is connected, Home Assistant can't read or control the K17 (see above).
- **No power control** - The K17 doesn't support network power on/off
- **No true mute** - Muting sets the volume to 0; unmuting does nothing
- **Reverse-engineered protocol** - Future firmware updates may break compatibility

## Command Line Testing

For testing outside of Home Assistant:

```bash
# From this component directory
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --info
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --set-volume 50
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --step -2
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --set-input optical
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --monitor 60
```

Add `--debug` to log connections and every frame the device sends that isn't used.

## Running Tests

The tests run the integration in a Home Assistant test instance against a simulated K17 (see [tests/conftest.py](tests/conftest.py)). No device is needed.

```bash
# From this component directory
pip install -r requirements_test.txt
pytest
```

To also run a smoke test against a real K17, disable the integration in Home Assistant and close the FiiO app first. The test sets the current volume and source again, so nothing audible changes:

```bash
pytest --live-host 192.168.1.100
```

## Technical Details

See [docs/protocol.md](docs/protocol.md) for the reverse-engineered protocol documentation, and [docs/captures/](docs/captures/) for the raw device captures behind it.

## License

MIT License - see [LICENSE](../../LICENSE) for details.

## Contributing

Issues and pull requests welcome.
