// Top processes: the programs that use the most CPU or memory
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""

    ColumnLayout {
        anchors.fill: parent
        spacing: 2
        RowLayout {
            Label { text: qsTr("Program"); color: card.subTextColor; font.pixelSize: card.unit * 0.9; Layout.fillWidth: true }
            Label { text: qsTr("CPU"); color: card.subTextColor; font.pixelSize: card.unit * 0.9; Layout.preferredWidth: card.unit * 5; horizontalAlignment: Text.AlignRight }
            Label { text: qsTr("Memory"); color: card.subTextColor; font.pixelSize: card.unit * 0.9; Layout.preferredWidth: card.unit * 6; horizontalAlignment: Text.AlignRight }
        }
        Repeater {
            model: info.rows || []
            delegate: RowLayout {
                Layout.fillWidth: true
                Label { text: modelData.name; color: card.textColor; font.pixelSize: card.unit * 1.1; elide: Text.ElideRight; Layout.fillWidth: true }
                Label { text: modelData.cpu; color: card.settings.sortBy === "memory" ? card.textColor : card.accent; font.pixelSize: card.unit * 1.1; Layout.preferredWidth: card.unit * 5; horizontalAlignment: Text.AlignRight }
                Label { text: modelData.memory; color: card.settings.sortBy === "memory" ? card.accent : card.textColor; font.pixelSize: card.unit * 1.1; Layout.preferredWidth: card.unit * 6; horizontalAlignment: Text.AlignRight }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
