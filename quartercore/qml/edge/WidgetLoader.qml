// Loads the QML component of one XENEON EDGE widget (kiosk and editor preview)
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Components instead of file URLs: loading a file of this folder by URL from
// here can deadlock Qt's type loader.

import QtQuick

Loader {
    id: loader
    property var widget: ({})
    readonly property var info: edge.data[widget.key] || ({})

    Component { id: clock; ClockWidget { widget: loader.widget; info: loader.info } }
    Component { id: weather; WeatherWidget { widget: loader.widget; info: loader.info } }
    Component { id: mediaPlayer; MediaWidget { widget: loader.widget; info: loader.info } }
    Component { id: battery; BatteryWidget { widget: loader.widget; info: loader.info } }
    Component { id: calendar; CalendarWidget { widget: loader.widget; info: loader.info } }
    Component { id: ring; RingWidget { widget: loader.widget; info: loader.info } }
    Component { id: history; HistoryWidget { widget: loader.widget; info: loader.info } }
    Component { id: cooling; CoolingWidget { widget: loader.widget; info: loader.info } }
    Component { id: profiles; ProfilesWidget { widget: loader.widget; info: loader.info } }
    Component { id: memory; MemoryWidget { widget: loader.widget; info: loader.info } }
    Component { id: storage; StorageWidget { widget: loader.widget; info: loader.info } }
    Component { id: custom; CustomWidget { widget: loader.widget; info: loader.info } }

    sourceComponent: ({
        "xeneon-clock": clock, "xeneon-weather": weather, "xeneon-media-player": mediaPlayer,
        "xeneon-battery-status": battery, "xeneon-calendar": calendar,
        "xeneon-cpu-temp": ring, "xeneon-cpu-load": ring, "xeneon-gpu-temp": ring, "xeneon-gpu-load": ring,
        "xeneon-device-temp": ring, "xeneon-device-rpm": ring, "xeneon-temperature-history": history,
        "xeneon-cooling-overview": cooling, "xeneon-profile-shortcuts": profiles, "xeneon-memory": memory,
        "xeneon-storage": storage, "custom": custom
    })[widget.template] || null
}
