// Cooling overview: temperatures and fan speeds of one device
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""

    Label {
        visible: (info.rows || []).length === 0
        anchors.centerIn: parent
        text: card.settings.deviceId ? qsTr("Unavailable") : qsTr("Choose a device in the layout editor")
        color: card.subTextColor
        font.pixelSize: card.unit * 1.1
    }
    Flickable {
        anchors.fill: parent
        contentHeight: list.height
        clip: true
        Column {
            id: list
            width: parent.width
            spacing: 8
            Repeater {
                model: info.rows || []
                delegate: Column {
                    width: list.width
                    spacing: 3
                    RowLayout {
                        width: parent.width
                        Label { text: modelData.name; color: card.textColor; font.pixelSize: card.unit * 1.05; elide: Text.ElideRight; Layout.fillWidth: true }
                        Label { text: modelData.temperature; color: card.subTextColor; font.pixelSize: card.unit * 1.05 }
                        Label { text: modelData.rpm; color: card.textColor; font.pixelSize: card.unit * 1.05; font.bold: true }
                    }
                    Rectangle {
                        visible: modelData.fill >= 0
                        width: parent.width; height: 5; radius: 2.5; color: "#232b36"
                        Rectangle { width: parent.width * Math.max(0, modelData.fill); height: parent.height; radius: 2.5; color: card.accent }
                    }
                }
            }
        }
    }
}
