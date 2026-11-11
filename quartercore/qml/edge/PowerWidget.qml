// Power: what the computer draws from the wall, through the power supply, with the cost
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""

    Label {
        visible: !info.available
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: qsTr("No power supply found")
        color: card.subTextColor
        font.pixelSize: card.unit * 1.1
    }
    ColumnLayout {
        visible: !!info.available
        anchors.fill: parent
        spacing: 4
        RowLayout {
            Label { text: info.watts || "–"; color: card.textColor; font.pixelSize: card.unit * 3; font.bold: true }
            Item { Layout.fillWidth: true }
            Column {
                Label { visible: !!info.costHour; text: qsTr("%1 per hour").arg(info.costHour || ""); color: card.textColor; font.pixelSize: card.unit * 1.1 }
                Label { visible: !!info.costDay; text: qsTr("%1 per day").arg(info.costDay || ""); color: card.subTextColor; font.pixelSize: card.unit }
            }
        }
        Label {
            text: qsTr("To the computer %1").arg(info.output || "–") + (info.efficiency ? " · " + qsTr("efficiency %1").arg(info.efficiency) : "")
            color: card.subTextColor
            font.pixelSize: card.unit
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
        MiniGraph {
            Layout.fillWidth: true
            Layout.fillHeight: true
            values: info.history || []
            color: card.accent
            slots: (card.settings.historyMinutes || 5) * 30
        }
    }
}
