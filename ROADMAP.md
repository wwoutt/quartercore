# Roadmap

Part 1 (steps 1-10) replaces web pages of OpenLinkHub with native pages. Until
a device has its own page, it opens in the OpenLinkHub web interface. Part 2
(steps A-G, below) moves the device control itself into Quartercore, so that
OpenLinkHub is no longer needed. Estimates are rough.

| # | Step | Status |
|---|---|---|
| 1 | Overview, iCUE LINK System Hub (speed, RGB, labels, brightness) | **done** (0.1) |
| 2 | Tray icon, start with the desktop session, settings (server URL, language) | **done** (0.2) |
| 3 | Temperature (speed) profiles: list, create, edit curves | **done** (0.3); probes, external sensors and the step table (graphProfiles off) still to do |
| 4 | RGB profiles and colour editing (static colours, effects, speed) | **done** (0.4); per-LED colours and the RGB cluster still to do |
| 5 | HX1500i and other power supplies | **done** (0.5) for HID power supplies; dongle power supplies still to do |
| 6 | K100 and other keyboards: lighting, profiles, key assignments, macros | **done** for the K100: part 1 (0.6) key colours, colour profiles, settings; part 2 (0.7) key assignments, macros with recording, performance, dial colours. Other keyboards (FlashTap, actuation, keyboards with modifier keys) still to test |
| 7 | HS80 MAX and other headsets: lighting, equalizer, sidetone, sleep | **done** (0.8) for the HS80 MAX WIRELESS: profiles, effect, brightness, zone colours, equalizer, sidetone, mic LED, sleep, buttons. Other headsets (Virtuoso with noise cancelling, HS80 RGB, VOID) still to do |
| 8 | XENEON EDGE: native kiosk on the XENEON EDGE, widgets, layout editor, store | **part 1 done** (0.9): native fullscreen kiosk with all 16 upstream widgets, the fork's layout and widget settings. The native layout editor came with step A (0.10). Own HTML widgets and the widget store came in 0.19 (see below). Still to do: touch testing on the real screen |
| 9 | Other device types (mice, controllers, LCDs, Commander hubs, memory) | later |
| 10 | Packaging (Flatpak), translations | later; Flatpak moves to step G |

## Notes for step 8 (XENEON EDGE)
Decided on 2026-11-10: the native kiosk is QML only. Custom HTML widgets from the
widget store of [wwoutt/OpenLinkHub](https://github.com/wwoutt/OpenLinkHub) are not
shown natively (a placeholder marks their place); a native widget format follows
later. Part 1 (0.9) has the kiosk and the 16 upstream widgets. Part 2:
- a native layout editor (drag, resize, hide), saved in the same layout file
  through `/api/xeneonLayout`, so the web editor keeps working,
- editing the widget settings (colours, texts, device, city, ...),
- a widget format and store,
- weather by device location (upstream asks the browser for it).

Changed on 2026-11-11 (0.19): the user chose own widgets in HTML after all, in a
sandboxed web view (QtWebEngine), with the format of the fork's custom widgets,
so they work in both. The store has its own catalog,
[wwoutt/quartercore-widgets](https://github.com/wwoutt/quartercore-widgets), and the
GitHub topic `quartercore-widget`. See [docs/WIDGETS.md](docs/WIDGETS.md).

## Part 2: Quartercore without OpenLinkHub
Decided on 2026-11-10: in the end Quartercore should run without OpenLinkHub.
Until now it is only a front end: OpenLinkHub drives the hardware (USB/HID),
runs the fan and pump control, the RGB effects, key assignments and macros,
reads the sensors and stores all profiles. This part moves that into
Quartercore, **one device at a time**, while OpenLinkHub keeps the others.

### How the switch works
- **A Quartercore service** (`quartercore-core`, Python, systemd user service)
  takes over from the OpenLinkHub service. It serves the **same HTTP API**
  that the Quartercore window uses now (the requests documented in
  `tests/fake_openlinkhub.py`), so the pages don't have to change.
- **Per device, OpenLinkHub or Quartercore.** Two programs can't drive the same
  USB device. OpenLinkHub can leave a device alone (its exclude list,
  `/api/setSupportedDevices`, by product id, after a restart of OpenLinkHub).
  `quartercore-core` drives the devices it has a driver for and passes every
  other request on to OpenLinkHub. When the last device has moved, OpenLinkHub
  can be removed.
- **Drivers are ports of OpenLinkHub's Go code** to Python. They stay GPL-3.0
  and keep the credit "based on OpenLinkHub by Nikola Jurković" in every file.
- **Access without root:** udev rules (like OpenLinkHub's `99-openlinkhub.rules`)
  give the logged-in user access to the Corsair `hidraw` devices and to
  `/dev/uinput` (for key assignments and macros). HID through `/dev/hidraw`
  with Python's standard library, so no new dependency.
- **Every step is tested by the user on the real hardware**; the fake
  OpenLinkHub and unit tests can't prove that a USB protocol is right.

### Steps, from low to high risk
| # | Step | What moves | Upstream code to port (lines) | Risk |
|---|---|---|---|---|
| A | XENEON EDGE kiosk on its own | **done** (0.10): own layout file with a native layout editor (drag, resize, show/hide, add/remove, widget settings, city search), taken over once from the fork; CPU/GPU, memory, storage and drive temperatures read directly; media player through MPRIS and wpctl. Still from OpenLinkHub until steps D-F: device sensors, batteries, device profiles. Not yet: editing on the touchscreen itself, weather by device location | `systeminfo` (665), `stats` (144), parts of `xeneonedge` | low, read only |
| B | `quartercore-core` and the HX1500i | **done** (0.11), switched over and tested on the real HX1500i on 2026-11-10 (readings, fan mode 40 % and back to default): the service (`python3 -m quartercore.core`, port 27013, same API, other requests passed on to OpenLinkHub, web pages redirected), takes a device over only when OpenLinkHub leaves it alone; udev rule (uaccess) and systemd user unit; power supplies: readings from the kernel driver corsair-psu (or over HID), fan mode over HID, back to the PSU's own curve on stop | `psuhid` (820) | low |
| C | XENEON EDGE device | **done** (0.12), switched over and tested on the real screen on 2026-11-10 (brightness 10 %/90 % seen by the user): brightness, contrast, backlight, colour tones and reset in quartercore-core (ported from `xeneonedge.go`), a native screen page that works with OpenLinkHub and with quartercore-core; device profiles of the screen not yet | `xeneonedge` (1063) | low |
| D | HS80 MAX WIRELESS | **done** (0.13), switched over and tested on the real headset on 2026-11-10 (firmware and battery read, zone colours and the red mic LED while muted seen by the user): dongle and headset in quartercore-core (software mode, heartbeat, events for battery, button, mute and on/off), device profiles, the RGB effect engine (`core/rgb.py`: the 16 headset modes), brightness, zone colours, mic LED, sidetone, sleep timer ("Off" works, upstream saves 15 minutes), button as profile switch; temperature effects get real temperatures. Still to do: the other button actions (uinput, with step E), applying the equalizer, muting the system microphone | `hs80maxW` (1957), `hs80maxdongle` (567), `rgb` | medium |
| E | K100 | in three parts. **E1 done** (0.14), tested on 2026-11-11 (HS80 scroll press as Play/Pause): virtual keyboard and mouse through uinput (`core/inputs.py`, OpenLinkHub's action table), macros played from OpenLinkHub's macro files (`core/macros.py`), all HS80 button actions. **E2 done** (0.15), switched over and tested on the real K100 on 2026-11-11 (colours, typing, control dial, lock key): the K100 in quartercore-core (`core/k100.py`) with key colours and colour profiles, effects (circle, circleshift and spinner added to `core/rgb.py`), brightness, layout, polling rate (the keyboard reconnects and is taken over again), control dial and its colours, debounce, performance with the lock key, device profiles, and the key assignments (they were planned for E3, but the lock and dial keys need the key reports anyway); the RGB effect settings of the lighting page for the K100 and HS80. **E3 done** (0.16): macros made, changed and played by quartercore-core (`core/macros.py`, `~/.config/Quartercore/core/macros/`, OpenLinkHub's macros copied once; a new step gets the next free number). Still to do: DPI and sniper actions (need a mouse driver), absolute mouse moves in macros | `k100` (3252), `inputmanager`, `macro`, `keyboards` | medium |
| F | iCUE LINK System Hub | in three parts. **F1 built** (0.17): watching only, quartercore-core works out the speeds OpenLinkHub sets (`core/cooling.py`: curves, failsafes, sensors) from OpenLinkHub's API, with its own and with OpenLinkHub's temperatures, shows them on the hub page and logs the changes; nothing goes to the hub. **F2**: take the hub over for RGB and readings, fans and pump on the hub's own curve (hardware mode). **F3**: fans and pump, with a watchdog and a safe fallback, after the log of F1 has been compared for some days | `lsh` (6087), `temperatures` | **high** |
| G | Remove OpenLinkHub | the proxy goes; Quartercore installs on its own; Flatpak (was step 10) | | low |

### Safety for step F (fans and pump)
- A bug in the fan or pump control can overheat the computer, so this step
  comes last, when the service has run reliably for weeks with the other devices.
- OpenLinkHub switches the hub to **hardware mode** when it stops
  (`setHardwareMode` in `lsh.go`), so the hub runs its own default curve.
  Quartercore does the same on stop. Still to find out: what the hub does when
  the controlling program **crashes** instead of stopping; if it keeps the last
  speed, the service needs a watchdog (systemd `WatchdogSec`) that falls back
  to hardware mode.
- Before Quartercore controls the speeds, it first runs alongside in read-only
  mode and logs what speeds it *would* set, to compare with OpenLinkHub.

### What this costs
- It is a large job: the five devices alone are about 14,000 lines of upstream
  Go, plus the shared parts (sensors, RGB effects, input, macros). Expect months.
- New devices and fixes from upstream OpenLinkHub no longer arrive on their
  own; they have to be ported by hand.
- Devices that aren't ported keep needing OpenLinkHub until step G.
