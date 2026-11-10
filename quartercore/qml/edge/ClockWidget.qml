// Date / Time
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls

EdgeCard {
    id: card
    property date now: new Date()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: card.now = new Date() }

    Column {
        anchors.verticalCenter: parent.verticalCenter
        x: Math.min(card.settings.left || 0, parent.width / 2)
        spacing: card.settings.subTop || 0
        Label {
            text: Qt.formatTime(card.now, "HH:mm")
            color: card.settings.textColor || "#e6e6e6"
            font.pixelSize: Math.min(card.settings.fontSize || 80, card.height * 0.45)
            font.bold: true
            topPadding: card.settings.top || 0
        }
        Label {
            text: card.now.toLocaleDateString(Qt.locale(), "dddd d MMMM")
            color: card.subTextColor
            font.pixelSize: Math.min(card.settings.subFontSize || 50, card.height * 0.18)
            leftPadding: card.settings.subLeft || 0
        }
    }
}
