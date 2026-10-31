# Home Assistant Projects

A collection of Home Assistant custom components and blueprints.

## Structure

```
blueprints/                                          # Home Assistant automation blueprints
  ├── now-playing-display-sync.yaml                  # Now Playing Display Sync
  ├── zha-candeo-sr5br-media-controls.yaml           # Candeo 5-Button Rotary Remote - Media Controls
  ├── zha-philips-hue-tap-dial-custom-controls.yaml  # Philips Hue Tap Dial - Custom Controls
  └── zha-philips-hue-tap-dial-media-controls.yaml   # Philips Hue Tap Dial - Media Controls
components/                                          # Custom integrations
  └── fiio_k17/                                      # FiiO K17 DAC/Amp control
```

## Components

### [FiiO K17](components/fiio_k17/)

A custom integration for controlling the FiiO K17 DAC/Amp volume over your local network.

**Installation:** Copy `components/fiio_k17/custom_components/fiio_k17/` to your Home Assistant's `custom_components/` directory.

## Blueprints

Automation blueprints for Zigbee remotes paired via ZHA and for media player displays.

To install, use the "Import Blueprint" button on the Blueprints Exchange post or in the description for the blueprint you want.

### [Candeo 5-Button Rotary Remote - Media Controls](blueprints/zha-candeo-sr5br-media-controls.yaml)

For the Candeo 5-Button Remote with Rotary Dial (C-ZB-SR5BR). Purpose-built for controlling media players. The center button toggles play/pause, buttons 1/2 handle previous/next track, and the dial adjusts volume by a configurable increment per click, with an optional maximum volume. Includes options for custom actions on single presses of buttons 3/4 and double presses, long presses, and long-press releases of all five buttons. Requires Home Assistant 2026.4 or later.

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fgtunes-dev%2Fha-toolkit%2Fblob%2Fmain%2Fblueprints%2Fzha-candeo-sr5br-media-controls.yaml)

### [Philips Hue Tap Dial - Media Controls](https://community.home-assistant.io/t/zha-philips-hue-tap-switch-mini-media-controls-rdm002/789650)

For the Philips Hue Tap Dial Switch (RDM002). Requires Home Assistant 2024.11 or later. Purpose-built for controlling media players (Sonos, Roon, etc.). Button 1 toggles play/pause, buttons 3/4 handle previous/next track, and the dial adjusts volume with velocity-sensitive control. Includes options for custom actions on multi-press events.

### [Philips Hue Tap Dial - Custom Controls](https://community.home-assistant.io/t/zha-philips-hue-tap-switch-mini-custom-controls-rdm002/789654)

A general-purpose framework for the Philips Hue Tap Dial Switch (RDM002). Requires Home Assistant 2024.10 or later. Provides a blank canvas where you define actions for every event: rotation (with velocity sensitivity), single/double/triple/quadruple presses, and long-press on all four buttons. Use this for non-media applications like lighting control, scene activation, or any other automation.

### [Now Playing Display Sync](blueprints/now-playing-display-sync.yaml)

Turns a "Now Playing" display on when a media player starts playing and off after playback stops, with a configurable delay so brief pauses don't put it to sleep. You supply the on and off actions, so it works with anything from a smart plug powering a dedicated screen to a tablet, TV input, or lighting scene. Requires Home Assistant 2024.6 or later.

[![Import Blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgist.github.com%2Fgtunes-dev%2Ff7c1f22c12308cf89f67f38ffb61fdad)

## License

MIT License - see [LICENSE](LICENSE) for details.
