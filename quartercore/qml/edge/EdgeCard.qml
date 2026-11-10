// The panel every XENEON EDGE widget sits in
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls

Rectangle {
    id: card
    property var widget: ({})
    property var info: ({})
    readonly property var settings: widget && widget.settings ? widget.settings : ({})
    readonly property color accent: settings.dataColor || "#38bdf8"
    readonly property color textColor: settings.textColor || "#e6e6e6"
    readonly property color subTextColor: settings.subTextColor || "#a1a1a1"
    // Text sizes follow the widget height, so small cells stay readable
    readonly property real unit: Math.max(10, Math.min(height / 14, width / 18))
    default property alias content: inner.data
    property alias title: heading.text

    radius: 14
    color: "#11151b"
    border.color: "#1f2630"
    clip: true

    Label {
        id: heading
        visible: text !== ""
        anchors { left: parent.left; top: parent.top; right: parent.right; margins: 14 }
        color: card.subTextColor
        font.pixelSize: Math.min(22, Math.max(13, card.settings.subFontSize || card.unit * 1.1))
        font.bold: true
        elide: Text.ElideRight
    }
    Item {
        id: inner
        anchors {
            left: parent.left; right: parent.right; bottom: parent.bottom
            top: heading.visible ? heading.bottom : parent.top
            margins: 14
        }
    }
}
