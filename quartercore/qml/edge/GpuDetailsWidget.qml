// GPU details: temperature, load, video memory, power, clocks and fan
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""

    component Bar: Rectangle {
        property real fraction: 0
        Layout.fillWidth: true
        height: 8; radius: 4; color: "#232b36"
        Rectangle { width: parent.width * Math.max(0, Math.min(1, parent.fraction)); height: parent.height; radius: 4; color: card.accent }
    }
    component Pair: Column {
        property string label
        property string value
        Layout.fillWidth: true
        Label { text: label; color: card.subTextColor; font.pixelSize: card.unit * 0.9 }
        Label { text: value; color: card.textColor; font.pixelSize: card.unit * 1.3; font.bold: true }
    }

    Label {
        visible: !info.available
        anchors.centerIn: parent
        text: qsTr("GPU data unavailable")
        color: card.subTextColor
        font.pixelSize: card.unit * 1.1
    }
    ColumnLayout {
        visible: !!info.available
        anchors.fill: parent
        spacing: 6
        Label { text: info.name || ""; color: card.textColor; font.pixelSize: card.unit * 1.2; elide: Text.ElideRight; Layout.fillWidth: true }
        RowLayout {
            Label { text: qsTr("Load"); color: card.subTextColor; font.pixelSize: card.unit; Layout.preferredWidth: card.unit * 6 }
            Bar { fraction: (info.load || 0) / 100 }
            Label { text: info.loadText || "–"; color: card.textColor; font.pixelSize: card.unit; Layout.preferredWidth: card.unit * 4 }
        }
        RowLayout {
            Label { text: qsTr("Memory"); color: card.subTextColor; font.pixelSize: card.unit; Layout.preferredWidth: card.unit * 6 }
            Bar { fraction: info.memoryFraction || 0 }
            Label { text: info.memory || "–"; color: card.textColor; font.pixelSize: card.unit; Layout.preferredWidth: card.unit * 9 }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 4
            Pair { label: qsTr("Temperature"); value: info.temperature || "–" }
            Pair { label: qsTr("Power"); value: info.power || "–" }
            Pair { label: qsTr("Fan"); value: info.fan || "–" }
            Pair { label: qsTr("Clock"); value: info.clock || "–" }
            Pair { label: qsTr("Memory clock"); value: info.memoryClock || "–" }
        }
        Item { Layout.fillHeight: true }
    }
}
