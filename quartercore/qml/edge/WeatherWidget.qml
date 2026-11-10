// Weather from Open-Meteo for the city set in OpenLinkHub
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    readonly property bool ok: !!info.available
    // The weather has the most lines; keep it inside its cell
    readonly property real u: Math.min(card.unit, card.height / 19)

    ColumnLayout {
        anchors.fill: parent
        spacing: 6
        Label {
            text: card.ok ? info.location : qsTr("Loading the weather…")
            color: card.subTextColor
            font.pixelSize: card.u * 1.2
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        RowLayout {
            visible: card.ok
            spacing: 18
            Label { text: info.icon || ""; font.pixelSize: card.u * 4.2 }
            Label {
                text: (info.temperature || "--") + (info.unit || "")
                color: card.textColor
                font.pixelSize: card.u * 4
                font.bold: true
            }
            ColumnLayout {
                spacing: 2
                Label { text: info.condition || ""; color: card.textColor; font.pixelSize: card.u * 1.3 }
                Label { text: qsTr("Feels like %1").arg(info.feelsLike || ""); color: card.subTextColor; font.pixelSize: card.u }
            }
        }
        RowLayout {
            visible: card.ok
            spacing: 22
            Label { text: "💧 " + (info.humidity || ""); color: card.subTextColor; font.pixelSize: card.u * 1.1 }
            Label { text: "💨 " + (info.wind || ""); color: card.subTextColor; font.pixelSize: card.u * 1.1 }
            Label { text: "☔ " + (info.rain || ""); color: card.subTextColor; font.pixelSize: card.u * 1.1 }
        }
        Item { Layout.fillHeight: true }
        RowLayout {
            visible: card.ok && (info.forecast || []).length > 0
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: info.forecast || []
                delegate: Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: col.implicitHeight + 12
                    radius: 10
                    color: "#18202a"
                    Column {
                        id: col
                        anchors.centerIn: parent
                        Label { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.time; color: card.subTextColor; font.pixelSize: card.u }
                        Label { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.temp; color: card.textColor; font.pixelSize: card.u * 1.4; font.bold: true }
                    }
                }
            }
        }
        Label {
            visible: card.ok
            text: qsTr("Updated %1").arg(info.updated || "")
            color: card.subTextColor
            opacity: 0.7
            font.pixelSize: card.u * 0.85
        }
    }
}
