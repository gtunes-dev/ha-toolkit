# Home Assistant Projects

A collection of Home Assistant custom components and blueprints.

## Structure

```
blueprints/          # Home Assistant automation blueprints
components/          # Custom integrations
  └── fiio_k17/      # FiiO K17 DAC/Amp control
```

## Components

### [FiiO K17](components/fiio_k17/)

A custom integration for controlling the FiiO K17 DAC/Amp volume over your local network.

**Installation:** Copy `components/fiio_k17/custom_components/fiio_k17/` to your Home Assistant's `custom_components/` directory.

## Blueprints

Blueprints for the Philips Hue Tap Dial Switch (RDM002) via ZHA. Requires Home Assistant 2024.10 or later.

To install, use the "Import Blueprint" button on the Blueprints Exchange post for the blueprint you want.

### [Philips Hue Tap Dial - Media Controls](https://community.home-assistant.io/t/zha-philips-hue-tap-switch-mini-media-controls-rdm002/789650)

Purpose-built for controlling media players (Sonos, Roon, etc.). Button 1 toggles play/pause, buttons 3/4 handle previous/next track, and the dial adjusts volume with velocity-sensitive control. Includes options for custom actions on multi-press events.

### [Philips Hue Tap Dial - Custom Controls](https://community.home-assistant.io/t/zha-philips-hue-tap-switch-mini-custom-controls-rdm002/789654)

A general-purpose framework for the Tap Dial. Provides a blank canvas where you define actions for every event: rotation (with velocity sensitivity), single/double/triple/quadruple presses, and long-press on all four buttons. Use this for non-media applications like lighting control, scene activation, or any other automation.

## License

MIT License - see [LICENSE](LICENSE) for details.
