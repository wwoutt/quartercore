// Storage overview: file systems and drive temperatures
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""

    Flickable {
        anchors.fill: parent
        contentHeight: list.height
        clip: true
        Column {
            id: list
            width: parent.width
            spacing: 10
            Label {
                visible: (info.rows || []).length === 0
                text: qsTr("No file systems")
                color: card.subTextColor
                font.pixelSize: card.unit * 1.1
            }
            Repeater {
                model: info.rows || []
                delegate: Column {
                    width: list.width
                    spacing: 3
                    RowLayout {
                        width: parent.width
                        Label { text: modelData.mountPoint; color: card.textColor; font.pixelSize: card.unit * 1.15; elide: Text.ElideMiddle; Layout.fillWidth: true }
                        Label { visible: modelData.hasData; text: modelData.percent.toFixed(1) + " %"; color: card.textColor; font.pixelSize: card.unit * 1.15; font.bold: true }
                    }
                    Label { text: modelData.device; color: card.subTextColor; font.pixelSize: card.unit * 0.9 }
                    Rectangle {
                        visible: modelData.hasData
                        width: parent.width; height: 6; radius: 3; color: "#232b36"
                        Rectangle { width: parent.width * Math.min(1, modelData.percent / 100); height: parent.height; radius: 3; color: card.accent }
                    }
                    Label {
                        visible: modelData.hasData
                        text: qsTr("Used %1 · Total %2 · Available %3").arg(modelData.used).arg(modelData.total).arg(modelData.free)
                        color: card.subTextColor
                        font.pixelSize: card.unit * 0.9
                    }
                }
            }
            Repeater {
                model: info.temperatures || []
                delegate: RowLayout {
                    width: list.width
                    Label { text: modelData.name; color: card.subTextColor; font.pixelSize: card.unit; elide: Text.ElideRight; Layout.fillWidth: true }
                    Label { text: modelData.value; color: card.textColor; font.pixelSize: card.unit; font.bold: true }
                }
            }
        }
    }
}
