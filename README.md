# Quartercore

**Control your Corsair devices on Linux from a native desktop program.**

The name: a *corsair* is a privateer ship, and its *quartermaster* looks after the
ship's gear. Quartercore does that for the gear in your computer, around its *core*.

Quartercore is a native KDE/Qt desktop program for [OpenLinkHub](https://github.com/jurkovic-nikola/OpenLinkHub),
the open-source Linux interface for Corsair devices by
**[Nikola Jurković](https://github.com/jurkovic-nikola)**.

OpenLinkHub runs as a service and is normally controlled from its web interface.
Quartercore controls the same service from a normal desktop window instead,
with the look of your KDE Plasma desktop. All credit for OpenLinkHub itself, the
device support and its API goes to Nikola Jurković and the OpenLinkHub contributors.

> **Not an official Corsair product**, and not affiliated with or endorsed by Corsair.
> Corsair, iCUE and XENEON are trademarks of Corsair, used here only to say which
> hardware OpenLinkHub works with. Not part of upstream OpenLinkHub and not maintained
> by its author: report problems [here](https://github.com/wwoutt/quartercore/issues).

## Who built this
Written by **Claude**, an AI model made by [Anthropic](https://www.anthropic.com),
in [Claude Code](https://claude.com/claude-code), on the direction and testing of
[wwoutt](https://github.com/wwoutt). It is tested on one machine (see below) and
not audited by an independent developer.

## What it is
- A **client** for the OpenLinkHub HTTP API. It sends the same requests as the
  OpenLinkHub web interface, so both can be used side by side.
- Version 0.6 has:
  - **Overview**: CPU and GPU temperature and load, memory, drive temperatures,
    and your devices.
  - **iCUE LINK System Hub**: every fan, pump and other device with live RPM and
    temperature, speed profile, RGB profile and label per device, and brightness,
    speed and lighting for all of them at once.
  - **Temperature profiles**: the built-in and your own profiles with their fan and
    pump curves; drag, add and remove points on your own curves; create profiles
    (CPU, GPU, liquid, drive, CPU + GPU or power supply sensor; curve, static or
    linear; zero RPM) and delete them. Uses OpenLinkHub's graph profiles
    (`"graphProfiles": true` in its `config.json`).
  - **Lighting**: the RGB effects of each device with a colour preview; set the two
    colours, the colours per temperature (CPU, GPU and liquid effects), a gradient
    with any number of colours, the probe range, speed, direction and alternating
    colours; use an effect on every device of a LINK System Hub in one click.
  - **Power supply** (HX1500i and other Corsair HID power supplies): power, output
    power, temperatures, fan speed and the 12V/5V/3.3V rails live, and the fan mode.
  - **Keyboard** (tested on the K100): the keyboard drawn with its key colours;
    select keys, rows or light zones and give them a colour; colour profiles (switch,
    save, save as, delete); effect, layout, polling rate, control dial and debounce
    time. Key assignments and macros are still in the web interface.
  - **Tray icon**: CPU and GPU temperature in the tooltip and menu, a speed profile
    for all fans and pump of a hub in two clicks, quick links to the XENEON EDGE
    layout and the web interface. Closing the window keeps Quartercore in the tray.
  - **Settings**: OpenLinkHub address, language (English, Dutch or the system
    language), start at login (optionally only in the tray), close to tray.
  - Starting Quartercore again shows the open window instead of a second copy.
  - Devices without a page yet open in the OpenLinkHub web interface.

## What it is not
- **Not a replacement for OpenLinkHub.** OpenLinkHub must be installed and running;
  this program only controls it.
- **Not complete.** Most device types (keyboards, mice, headsets, USB-dongle power supplies,
  LCDs, per-LED colours, macros) still use the web interface. Temperature profiles
  with probes, external sensors or multiple GPUs, and the step table used when
  `graphProfiles` is off, are only in the web interface for now.
  See [ROADMAP.md](ROADMAP.md).
- **Not iCUE**, and not for Windows or macOS.

## Requirements
- [OpenLinkHub](https://github.com/jurkovic-nikola/OpenLinkHub) running on
  `http://127.0.0.1:27003` (or pass `--url`)
- Python 3 with PySide6 6.5 or newer (Qt 6). Fedora / Bazzite: included, or
  `sudo dnf install python3-pyside6`. Debian/Ubuntu: `sudo apt install python3-pyside6.qtquick`.
- Best on KDE Plasma 6 (uses the Plasma style), works on other desktops with the
  Fusion style.

## Install
```bash
./install.sh            # installs for your user, adds "Quartercore" to the menu
./install.sh --remove   # uninstalls
```
Or run it from the source folder: `python3 -m quartercore [--url http://host:port]`.

## Tested on
Bazzite 44 (Fedora Atomic), KDE Plasma 6, PySide6 6.11, OpenLinkHub 0.9.4 with an
iCUE LINK System Hub (12 RX RGB fans and a TITAN 360 AIO).

## Development
- `python3 -m unittest discover -s tests`: tests against a fake OpenLinkHub
  (they never touch real hardware)
- `python3 tests/fake_openlinkhub.py`: the fake on port 27099, to try Quartercore
  without changing your real profiles: `python3 -m quartercore --url http://127.0.0.1:27099`
- `tools/screenshot.sh out.png [serial|settings|profiles[:name]] [--fake]`: grabs the
  window offscreen against the running OpenLinkHub or the fake
- `tools/tray-check.sh`: checks the tray icon and the single instance in your desktop session
- Translations: `quartercore/i18n/<language>.json` maps the English texts to the
  translation; the tests fail when a text has no Dutch translation

## License
[GPL-3.0](LICENSE) or later, like OpenLinkHub.
