# Roadmap

Each step replaces web pages of OpenLinkHub with native pages. Until a device
has its own page, it opens in the OpenLinkHub web interface. Estimates are rough.

| # | Step | Status |
|---|---|---|
| 1 | Overview, iCUE LINK System Hub (speed, RGB, labels, brightness) | **done** (0.1) |
| 2 | Tray icon, start with the desktop session, settings (server URL, language) | **done** (0.2) |
| 3 | Temperature (speed) profiles: list, create, edit curves | **done** (0.3); probes, external sensors and the step table (graphProfiles off) still to do |
| 4 | RGB profiles and colour editing (static colours, effects, speed) | **done** (0.4); per-LED colours and the RGB cluster still to do |
| 5 | HX1500i and other power supplies | **done** (0.5) for HID power supplies; dongle power supplies still to do |
| 6 | K100 and other keyboards: lighting, profiles, key assignments, macros | **part 1 done** (0.6): key colours, colour profiles, settings; key assignments, macros, performance and dial colours still to do |
| 7 | HS80 MAX and other headsets: lighting, equalizer, sidetone, sleep | planned |
| 8 | XENEON EDGE: native kiosk on the XENEON EDGE, widgets, layout editor, store | planned |
| 9 | Other device types (mice, controllers, LCDs, Commander hubs, memory) | later |
| 10 | Packaging (Flatpak), translations | later |

## Notes for step 8 (XENEON EDGE)
The current kiosk, custom widgets and widget store of
[wwoutt/OpenLinkHub](https://github.com/wwoutt/OpenLinkHub) are HTML. A native
XENEON EDGE needs:
- a fullscreen Qt window on the 2560×720 output (the KWin rule and touch mapping
  from the fork can stay),
- native versions of the upstream widgets (clock, weather, system values, devices,
  media player, ...),
- a native layout editor (drag, resize, hide), stored in the same layout file so the
  web editor keeps working,
- a decision for custom widgets from the store: either a native widget format (QML)
  or showing HTML widgets in a sandboxed web view inside the Qt window. Existing HTML
  widgets only keep working with the second option.
