// A custom HTML widget from the widget store: not shown in the native kiosk
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls

EdgeCard {
    id: card
    color: "#0d1116"
    border.color: "#1a2029"
    Label {
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: qsTr("HTML widget \"%1\" is only shown in the web kiosk").arg(card.widget.name || "")
        color: card.subTextColor
        font.pixelSize: card.unit
    }
}
