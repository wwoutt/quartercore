# OpenLinkHub Desktop

A native KDE/Qt desktop program for [OpenLinkHub](https://github.com/jurkovic-nikola/OpenLinkHub),
the open-source Linux interface for Corsair devices by
**[Nikola Jurković](https://github.com/jurkovic-nikola)**.

OpenLinkHub runs as a service and is normally controlled from its web interface.
OpenLinkHub Desktop controls the same service from a normal desktop window instead,
with the look of your KDE Plasma desktop. All credit for OpenLinkHub itself, the
device support and its API goes to Nikola Jurković and the OpenLinkHub contributors.

> **Not an official Corsair product**, and not affiliated with or endorsed by Corsair.
> Corsair, iCUE and XENEON are trademarks of Corsair, used here only to say which
> hardware OpenLinkHub works with. Not part of upstream OpenLinkHub and not maintained
> by its author: report problems [here](https://github.com/wwoutt/openlinkhub-desktop/issues).

## Who built this
Written by **Claude**, an AI model made by [Anthropic](https://www.anthropic.com),
in [Claude Code](https://claude.com/claude-code), on the direction and testing of
[wwoutt](https://github.com/wwoutt). It is tested on one machine (see below) and
not audited by an independent developer.

## What it is
- A **client** for the OpenLinkHub HTTP API. It sends the same requests as the
  OpenLinkHub web interface, so both can be used side by side.
- Version 0.1 (milestone 1) has:
  - **Overview**: CPU and GPU temperature and load, memory, drive temperatures,
    and your devices.
  - **iCUE LINK System Hub**: every fan, pump and other device with live RPM and
    temperature, speed profile, RGB profile and label per device, and brightness,
    speed and lighting for all of them at once.
  - Devices without a page yet open in the OpenLinkHub web interface.

## What it is not
- **Not a replacement for OpenLinkHub.** OpenLinkHub must be installed and running;
  this program only controls it.
- **Not complete.** Most device types (keyboards, mice, headsets, power supplies,
  LCDs, the RGB editor, temperature profiles, macros) still use the web interface.
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
./install.sh            # installs for your user, adds "OpenLinkHub Desktop" to the menu
./install.sh --remove   # uninstalls
```
Or run it from the source folder: `python3 -m openlinkhub_desktop [--url http://host:port]`.

## Tested on
Bazzite 44 (Fedora Atomic), KDE Plasma 6, PySide6 6.11, OpenLinkHub 0.9.4 with an
iCUE LINK System Hub (12 RX RGB fans and a TITAN 360 AIO).

## Development
- `python3 -m unittest discover -s tests`: tests against a fake OpenLinkHub
  (they never touch real hardware)
- `tools/screenshot.sh out.png [serial]`: grabs the window offscreen against a running
  OpenLinkHub

## License
[GPL-3.0](LICENSE) or later, like OpenLinkHub.
