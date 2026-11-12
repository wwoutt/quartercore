// Battery status of wireless devices
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
// Modified by wwoutt, 2026-11-12: also other devices (Razer, Bluetooth, ...), a charging sign and a message

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: qsTr("Battery")

    Label {
        visible: (info.rows || []).length === 0
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: info.message || qsTr("No wireless devices")
        color: card.subTextColor
        font.pixelSize: card.unit * 1.2
    }
    Column {
        anchors.fill: parent
        spacing: 10
        Repeater {
            model: info.rows || []
            delegate: Column {
                width: parent.width
                spacing: 4
                RowLayout {
                    width: parent.width
                    Label { text: modelData.name; color: card.textColor; font.pixelSize: card.unit * 1.2; elide: Text.ElideRight; Layout.fillWidth: true }
                    Label { visible: !!modelData.charging; text: "⚡"; color: card.accent; font.pixelSize: card.unit * 1.2 }
                    Label { text: modelData.level + " %"; color: card.textColor; font.pixelSize: card.unit * 1.2; font.bold: true }
                }
                Rectangle {
                    width: parent.width; height: 6; radius: 3; color: "#232b36"
                    Rectangle {
                        width: parent.width * modelData.level / 100; height: parent.height; radius: 3
                        color: modelData.level <= 20 ? "#f87171" : card.accent
                    }
                }
            }
        }
        Label {
            visible: (info.rows || []).length > 0 && !!info.message
            width: parent.width
            wrapMode: Text.WordWrap
            text: info.message || ""
            color: card.subTextColor
            font.pixelSize: card.unit * 0.9
        }
    }
}
