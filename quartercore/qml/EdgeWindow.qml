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

    Repeater {
        model: edge.items
        delegate: WidgetLoader {
            required property var modelData
            widget: modelData
            x: modelData.x * win.cellW + win.margin
            y: modelData.y * win.cellH + win.margin
            width: modelData.w * win.cellW - 2 * win.margin
            height: modelData.h * win.cellH - 2 * win.margin
        }
    }

    // Device widgets, batteries and profiles still come from OpenLinkHub
    Label {
        visible: !backend.connected && edge.items.some(i => ["xeneon-device-temp", "xeneon-device-rpm",
            "xeneon-cooling-overview", "xeneon-profile-shortcuts", "xeneon-battery-status"].indexOf(i.template) >= 0)
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter; bottomMargin: 4 }
        text: qsTr("Not connected to OpenLinkHub")
        color: "#a1a1a1"
        font.pixelSize: 13
    }
}
