// System info: computer, operating system, kernel, CPU, uptime and load
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""

    GridLayout {
        visible: !!info.available
        anchors.fill: parent
        columns: 2
        columnSpacing: card.unit
        rowSpacing: 2
        Repeater {
            model: [
                [qsTr("Computer"), info.host], [qsTr("System"), info.os], [qsTr("Kernel"), info.kernel],
                [qsTr("Processor"), info.cpu], [qsTr("Running for"), info.uptime],
                [qsTr("Load (1, 5, 15 min)"), info.load], [qsTr("Processes"), info.processes]
            ]
            delegate: Item {
                Layout.columnSpan: 2
                Layout.fillWidth: true
                implicitHeight: line.implicitHeight
                RowLayout {
                    id: line
                    width: parent.width
                    Label { text: modelData[0]; color: card.subTextColor; font.pixelSize: card.unit; Layout.preferredWidth: card.unit * 10; elide: Text.ElideRight }
                    Label { text: modelData[1] || "–"; color: card.textColor; font.pixelSize: card.unit * 1.1; Layout.fillWidth: true; elide: Text.ElideRight }
                }
            }
        }
        Item { Layout.columnSpan: 2; Layout.fillHeight: true }
    }
}
