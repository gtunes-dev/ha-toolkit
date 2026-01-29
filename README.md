# FiiO K17 Control

A Home Assistant custom integration for controlling the FiiO K17 DAC/Amp volume over your local network.

I built this integration because I wanted to use my [Philips Hue Tap Dial Switch](https://community.home-assistant.io/t/zha-philips-hue-tap-switch-mini-custom-controls-rdm002/789654) (for which I also wrote a blueprint) to control my K17's volume. Now you can adjust the K17's volume from any Home Assistant automation, dashboard, or physical controller.

**Note:** This integration only supports volume control. The K17's network protocol does not support transport controls (play/pause/skip) when using streaming sources like USB or Bluetooth.

> **⚠️ Single Connection Limit:** The K17 only accepts one network connection at a time. When this integration is connected, you cannot use the FiiO Control phone app (and vice versa). This is a hardware limitation of the device.

## Features

- **Volume control** via Home Assistant media player entity
- **Real-time updates** when the physical volume knob is turned
- **Simple setup** via the Home Assistant UI

## Requirements

- Home Assistant 2023.1 or later
- FiiO K17 connected to your local network (same network as HA)
- The device's IP address

## Installation

1. Download or clone this repository

2. Copy the `custom_components/fiio_k17` folder to your Home Assistant config directory:
   ```
   <ha-config>/custom_components/fiio_k17/
   ```

3. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **FiiO K17**
4. Enter your device's IP address

The integration will create a media player entity with volume control.

## Usage

Once configured, you can:

- **Control volume** via the media player card or slider
- **Use in automations** with the `media_player.volume_set` service
- **Monitor volume** - the entity updates when the physical knob is turned

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

## Troubleshooting

### "Cannot connect" error during setup

1. **Close the FiiO Control app** - The K17 only accepts one connection at a time
2. **Verify the IP address** - Check your router or the FiiO Control app for the correct IP
3. **Check network connectivity** - Ensure HA can reach the device (same VLAN/subnet)

### Volume changes not reflected in HA

- The integration uses push updates. If the connection drops, restart the integration.

### Finding your K17's IP address

- Check your router's DHCP client list
- Use the FiiO Control app (Settings → Device Info)
- The device hostname is typically `fiio_k17`

## Limitations

- **Single client only** - The K17 only accepts one TCP connection. Close the FiiO Control app before using this integration.
- **No power control** - The K17 doesn't support network power on/off
- **Reverse-engineered protocol** - Future firmware updates may break compatibility

## Command Line Testing

For testing outside of Home Assistant:

```bash
# From the repository root
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --info
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --set-volume 50
python3 custom_components/fiio_k17/cli.py 192.168.1.100 --monitor
```

## Technical Details

See [docs/protocol.md](docs/protocol.md) for the reverse-engineered protocol documentation.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Issues and pull requests welcome at [github.com/gtunes-dev/fiio-k17-control](https://github.com/gtunes-dev/fiio-k17-control).
