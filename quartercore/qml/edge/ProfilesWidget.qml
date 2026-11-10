// Profile shortcuts: switch the profile of one device with a touch
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls

EdgeCard {
    id: card
    title: settings.headerText || ""

    Label {
        visible: (info.profiles || []).length === 0
        anchors.centerIn: parent
        text: !card.settings.deviceId ? qsTr("Choose a device in the layout editor")
            : info.available ? qsTr("No profiles") : qsTr("Unavailable")
        color: card.subTextColor
        font.pixelSize: card.unit * 1.1
    }
    Flow {
        anchors.fill: parent
        spacing: 10
        Repeater {
            model: info.profiles || []
            // Big touch targets; the desktop style would draw small buttons
            delegate: Rectangle {
                width: name.implicitWidth + 40
                height: Math.max(48, name.implicitHeight + 24)
                radius: 10
                color: modelData.active ? card.accent : touch.pressed ? "#243040" : "#18202a"
                border.color: modelData.active ? card.accent : "#2a3442"
                Label {
                    id: name
                    anchors.centerIn: parent
                    text: modelData.name
                    color: modelData.active ? "#07090c" : card.textColor
                    font.pixelSize: Math.min(card.settings.fontSize || 20, card.unit * 1.6)
                    font.bold: modelData.active
                }
                MouseArea {
                    id: touch
                    anchors.fill: parent
                    onClicked: if (!modelData.active) edge.changeProfile(card.settings.deviceId, modelData.name)
                }
            }
        }
    }
}
