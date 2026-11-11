// Network: download and upload speed with a graph of the last minute
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""
    readonly property color upColor: settings.uploadColor || "#f472b6"

    Label {
        visible: !info.available
        anchors.centerIn: parent
        text: qsTr("Measuring the network…")
        color: card.subTextColor
        font.pixelSize: card.unit * 1.1
    }
    ColumnLayout {
        visible: !!info.available
        anchors.fill: parent
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            spacing: card.unit
            Column {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Label { text: "↓ " + qsTr("Download"); color: card.accent; font.pixelSize: card.unit }
                Label { text: info.down || "–"; color: card.textColor; font.pixelSize: card.unit * 2; font.bold: true }
            }
            Column {
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                Label { text: "↑ " + qsTr("Upload"); color: card.upColor; font.pixelSize: card.unit }
                Label { text: info.up || "–"; color: card.textColor; font.pixelSize: card.unit * 2; font.bold: true }
            }
        }
        Label { text: qsTr("Peak %1").arg(info.peak || "–"); color: card.subTextColor; font.pixelSize: card.unit * 0.9 }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            MiniGraph { anchors.fill: parent; values: info.downHistory || []; color: card.accent; slots: card.settings.historySeconds || 60 }
            MiniGraph { anchors.fill: parent; values: info.upHistory || []; color: card.upColor; slots: card.settings.historySeconds || 60 }
        }
    }
}
