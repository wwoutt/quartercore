// The XENEON EDGE kiosk: a fullscreen window with the widgets on a 24 x 12 grid
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Native version of the OpenLinkHub kiosk page with the layout of the fork
// wwoutt/OpenLinkHub. The widgets are in qml/edge/.

import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "edge"

Window {
    id: win
    title: qsTr("Quartercore XENEON EDGE")
    width: 2560
    height: 720
    color: "#07090c"
    flags: Qt.FramelessWindowHint

    readonly property real cellW: width / edge.columns
    readonly property real cellH: height / edge.rows
    readonly property int margin: 6

    onVisibleChanged: edge.setActive(visible)
    Component.onCompleted: edge.setActive(visible)

    readonly property var components: ({
        "xeneon-clock": "edge/ClockWidget.qml",
        "xeneon-weather": "edge/WeatherWidget.qml",
        "xeneon-media-player": "edge/MediaWidget.qml",
        "xeneon-battery-status": "edge/BatteryWidget.qml",
        "xeneon-calendar": "edge/CalendarWidget.qml",
        "xeneon-cpu-temp": "edge/RingWidget.qml",
        "xeneon-cpu-load": "edge/RingWidget.qml",
        "xeneon-gpu-temp": "edge/RingWidget.qml",
        "xeneon-gpu-load": "edge/RingWidget.qml",
        "xeneon-device-temp": "edge/RingWidget.qml",
        "xeneon-device-rpm": "edge/RingWidget.qml",
        "xeneon-temperature-history": "edge/HistoryWidget.qml",
        "xeneon-cooling-overview": "edge/CoolingWidget.qml",
        "xeneon-profile-shortcuts": "edge/ProfilesWidget.qml",
        "xeneon-memory": "edge/MemoryWidget.qml",
        "xeneon-storage": "edge/StorageWidget.qml",
        "custom": "edge/CustomWidget.qml"
    })

    Repeater {
        model: edge.items
        delegate: Loader {
            required property var modelData
            x: modelData.x * win.cellW + win.margin
            y: modelData.y * win.cellH + win.margin
            width: modelData.w * win.cellW - 2 * win.margin
            height: modelData.h * win.cellH - 2 * win.margin
            source: win.components[modelData.template] || ""
            onLoaded: {
                item.widget = Qt.binding(() => modelData)
                item.info = Qt.binding(() => edge.data[modelData.key] || ({}))
            }
        }
    }

    // OpenLinkHub doesn't see the XENEON EDGE, or isn't running
    Label {
        visible: edge.status !== "" || !backend.connected
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 4 }
        text: backend.connected ? edge.status : qsTr("Not connected to OpenLinkHub")
        color: "#a1a1a1"
        font.pixelSize: 13
    }
}
