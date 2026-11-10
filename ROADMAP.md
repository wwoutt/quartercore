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
| 6 | K100 and other keyboards: lighting, profiles, key assignments, macros | **done** for the K100: part 1 (0.6) key colours, colour profiles, settings; part 2 (0.7) key assignments, macros with recording, performance, dial colours. Other keyboards (FlashTap, actuation, keyboards with modifier keys) still to test |
| 7 | HS80 MAX and other headsets: lighting, equalizer, sidetone, sleep | **done** (0.8) for the HS80 MAX WIRELESS: profiles, effect, brightness, zone colours, equalizer, sidetone, mic LED, sleep, buttons. Other headsets (Virtuoso with noise cancelling, HS80 RGB, VOID) still to do |
| 8 | XENEON EDGE: native kiosk on the XENEON EDGE, widgets, layout editor, store | **part 1 done** (0.9): native fullscreen kiosk with all 16 upstream widgets, the fork's layout and widget settings. Still to do: native layout editor (drag, resize, hide, widget settings), a native widget format for the store (decided: no HTML widgets), touch testing on the real screen |
| 9 | Other device types (mice, controllers, LCDs, Commander hubs, memory) | later |
| 10 | Packaging (Flatpak), translations | later |

## Notes for step 8 (XENEON EDGE)
Decided on 2026-11-10: the native kiosk is QML only. Custom HTML widgets from the
widget store of [wwoutt/OpenLinkHub](https://github.com/wwoutt/OpenLinkHub) are not
shown natively (a placeholder marks their place); a native widget format follows
later. Part 1 (0.9) has the kiosk and the 16 upstream widgets. Part 2:
- a native layout editor (drag, resize, hide), saved in the same layout file
  through `/api/xeneonLayout`, so the web editor keeps working,
- editing the widget settings (colours, texts, device, city, ...),
- a native widget format and store,
- weather by device location (upstream asks the browser for it).
