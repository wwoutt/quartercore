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
- Version 0.16 has:
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
    time; **key assignments** per key (media keys, keyboard keys, mouse buttons,
    macros, DPI, sniper, scroll, zoom, profile change and more, with default action,
    press and hold and toggle delay); **performance** (disable the Win key,
    Alt + Tab, Shift + Tab, Alt + F4); the **control dial colours**.
  - **Macros**: create and delete macros, add steps (keyboard key, mouse button,
    delay, text, mouse position), change hold, repeat and delay per step, delete
    steps, loop or repeat a macro, and **record** key presses in the window (with
    the pauses between them). Keys the desktop takes itself, like Alt + Tab, can't
    be recorded.
  - **Headset** (tested on the HS80 MAX WIRELESS): battery level, device profiles
    (switch, save as, delete), RGB effect, brightness and zone colours, the
    10-band equalizer (-12 to +12 dB, flat), sidetone on/off and level, mic LED,
    sleep timer, and the assignment of its buttons. Like the web interface, the
    settings only show while the headset is switched on.
  - **XENEON EDGE kiosk** (native, off by default): a fullscreen window on the
    2560 × 720 output with all 16 OpenLinkHub widgets made in QML: date and time,
    weather (Open-Meteo, for the city set in OpenLinkHub), media player with
    buttons, battery status, calendar, CPU/GPU temperature and load, device
    temperature and RPM, temperature history, cooling overview, profile shortcuts,
    memory and storage. CPU and GPU temperature and load, memory, storage and
    the media player (MPRIS) are read by Quartercore itself; device sensors,
    batteries and device profiles still come from OpenLinkHub. Custom HTML
    widgets from the widget store are not shown, and the weather doesn't use the
    device location. Turn it on in the settings or the tray menu, after turning
    off the fork's web kiosk.
  - **XENEON EDGE layout editor** (native): the kiosk as a live preview; drag
    widgets to move them and the corner to resize them on the 24 × 12 grid,
    show, hide, add and remove widgets, and change their settings (colours,
    texts, sizes, scale, unit, device and sensor, city with search, ...).
    Quartercore keeps the layout in `~/.config/Quartercore/xeneon-edge.json`;
    the first time it takes over the layout of the fork's web editor and the
    widget settings of OpenLinkHub, when there are any. All 16 widgets can be
    shown at once.
  - **XENEON EDGE screen**: brightness, contrast, backlight and the red, green
    and blue colour tones, and reset to the factory values.
  - **Tray icon**: CPU and GPU temperature in the tooltip and menu, a speed profile
    for all fans and pump of a hub in two clicks, quick links to the XENEON EDGE
    layout and the web interface. Closing the window keeps Quartercore in the tray.
  - **Settings**: OpenLinkHub address, language (English, Dutch or the system
    language), start at login (optionally only in the tray), close to tray.
  - Starting Quartercore again shows the open window instead of a second copy.
  - Devices without a page yet open in the OpenLinkHub web interface.

## What it is not
- **Not a replacement for OpenLinkHub (yet).** OpenLinkHub must be installed and
  running; this program only controls it. Moving the device control into
  Quartercore, one device at a time, is planned in [ROADMAP.md](ROADMAP.md) (part 2).
- **Not complete.** Most device types (other keyboards than the K100, mice, other
  headsets than the HS80 MAX WIRELESS, USB-dongle power supplies, LCDs, per-LED
  colours) still use the web interface. Temperature profiles
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

## quartercore-core: devices without OpenLinkHub (test phase)
`quartercore-core` is a small service that drives devices itself and passes
everything else on to OpenLinkHub ([ROADMAP.md](ROADMAP.md), part 2). It speaks
the same API, so the Quartercore window only needs its address changed. So far
it drives:
- **Corsair HID power supplies** (HX1500i and the others OpenLinkHub supports):
  readings from the kernel driver `corsair-psu` when it is loaded, otherwise over
  USB, and the fan mode over USB. On stop the fan goes back to the power supply's
  own curve.
- **The XENEON EDGE screen**: brightness, contrast, backlight and colour tones.
  On stop it gets the values OpenLinkHub sets when it stops.
- **The HS80 MAX WIRELESS headset** (through its USB dongle): battery, device
  profiles, the RGB effects (zone colours, static, off and the animated effects,
  ported from OpenLinkHub), brightness, mic LED, sidetone, sleep timer and the
  button (media keys, keys, mouse buttons, macros and profile switch). On stop
  the dongle and headset go back to hardware mode. Not yet: the equalizer is
  saved but not applied, as OpenLinkHub does with its audio module off; muting
  only changes the mic LED. On the first start it takes over OpenLinkHub's
  headset profiles, button and RGB settings.
- **The K100 keyboard**: key colours and colour profiles, the RGB effects (also
  circle, circleshift and spinner), brightness, layout, polling rate, control dial
  (volume, brightness, scroll, zoom, screen brightness, media, horizontal scroll)
  and its colours, debounce time, performance (with the lock key), device profiles
  and key assignments (media keys, keys, mouse buttons, macros, scroll, zoom,
  screen brightness, profile change). On stop it goes back to hardware mode. Not
  yet: DPI and sniper actions (they need a mouse driven by quartercore-core),
  OpenRGB and the RGB cluster. Layouts are read from OpenLinkHub's
  `database/keyboard`. On the first start it takes over OpenLinkHub's profile.
- **A virtual keyboard and mouse** (`/dev/uinput`) for button actions and macros,
  made the first time a button needs them. Moving the mouse to an absolute
  position isn't ported yet.
- **Macros**: made, changed and played by quartercore-core, stored in
  `~/.config/Quartercore/core/macros/` (OpenLinkHub's macros are copied the first
  time). A new step gets the next free number, so it never replaces a step after
  a deleted one, as it can in OpenLinkHub.

It only takes over a device when OpenLinkHub runs and leaves that device alone,
so the two never drive the same device. `./install.sh` installs it, but it
doesn't start until you enable it.

**Switch the power supply over** (product id 7199 is the HX1500i):
```bash
sudo install -m 644 data/udev/71-quartercore.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw
curl -s -X POST http://127.0.0.1:27003/api/setSupportedDevices -d '{"supportedDevices": {"7199": false}}'
sudo systemctl restart OpenLinkHub
systemctl --user enable --now quartercore-core
```
Then set the address in Quartercore's settings to `http://127.0.0.1:27013`.

**Switch the XENEON EDGE over** (product id 7437). Once OpenLinkHub leaves it
alone, the fork's web kiosk and web layout editor stop working; the native kiosk
doesn't need them. To keep the layout of the web editor, use "Take over from
OpenLinkHub" in Quartercore's layout editor first.
```bash
sudo install -m 644 data/udev/71-quartercore.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw
curl -s -X POST http://127.0.0.1:27003/api/setSupportedDevices -d '{"supportedDevices": {"7437": false}}'
sudo systemctl restart OpenLinkHub
```
quartercore-core takes it over within ten seconds. Back: the same with `true`
and a restart of OpenLinkHub.

Since 0.14 the udev rule also gives you `/dev/uinput`; after updating, install
the rule again (the first two lines below) and run
`sudo udevadm trigger --subsystem-match=misc --sysname-match=uinput`.

**Switch the HS80 MAX WIRELESS over** (product id 2711 is its dongle):
```bash
sudo install -m 644 data/udev/71-quartercore.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw
curl -s -X POST http://127.0.0.1:27003/api/setSupportedDevices -d '{"supportedDevices": {"2711": false}}'
sudo systemctl restart OpenLinkHub
```
Back: the same with `true` and a restart of OpenLinkHub.

**Switch the K100 over** (product id 7109; 7036 and 7037 for the other K100
models). Keep a second keyboard or the mouse at hand: if something goes wrong,
the way back is the same `curl` line with `true` and a restart of OpenLinkHub.
```bash
sudo install -m 644 data/udev/71-quartercore.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw
curl -s -X POST http://127.0.0.1:27003/api/setSupportedDevices -d '{"supportedDevices": {"7109": false}}'
sudo systemctl restart OpenLinkHub
```
`curl -s http://127.0.0.1:27013/api/core` shows which devices it drives, and
`journalctl --user -u quartercore-core` what it did.

**Back to OpenLinkHub:**
```bash
systemctl --user disable --now quartercore-core
curl -s -X POST http://127.0.0.1:27003/api/setSupportedDevices -d '{"supportedDevices": {"7199": true, "7437": true, "2711": true, "7109": true}}'
sudo systemctl restart OpenLinkHub
```
and set the address back to `http://127.0.0.1:27003`.

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
