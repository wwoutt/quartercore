// Overview: system values and the connected devices
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// A Flickable instead of a ScrollView: no width binding loop with the KDE style
Flickable {
    id: page
    contentHeight: content.implicitHeight
    clip: true
    ScrollBar.vertical: ScrollBar {}
    readonly property real availableWidth: width - 12
    readonly property var sys: backend.system

    ColumnLayout {
        id: content
        width: page.availableWidth
        spacing: 16

        Label {
            text: qsTr("Overview")
            font.pixelSize: 26
            Layout.leftMargin: 24
            Layout.topMargin: 20
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            columns: Math.max(1, Math.floor((page.availableWidth - 48) / 230))
            columnSpacing: 12
            rowSpacing: 12

            StatCard { title: qsTr("CPU temperature"); value: sys.cpuTemp || "–" }
            StatCard { title: qsTr("CPU load"); value: sys.cpuLoad !== undefined ? Math.round(sys.cpuLoad) + " %" : "–" }
            StatCard { title: qsTr("GPU temperature"); value: sys.gpuTemp || "–" }
            StatCard { title: qsTr("GPU load"); value: sys.gpuLoad !== undefined ? Math.round(sys.gpuLoad) + " %" : "–" }
            StatCard {
                title: qsTr("Memory")
                value: sys.memory ? Math.round(sys.memory.UsedPercent) + " %" : "–"
                detail: sys.memory ? qsTr("%1 of %2 GB").arg((sys.memory.Used / 1073741824).toFixed(1))
                                     .arg((sys.memory.Total / 1073741824).toFixed(0)) : ""
            }
            Repeater {
                model: sys.storage || []
                StatCard { title: modelData.Model; value: modelData.TemperatureString }
            }
        }

        Label {
            text: qsTr("Devices")
            font.pixelSize: 18
            Layout.leftMargin: 24
            Layout.topMargin: 8
        }

        Repeater {
            model: backend.devices
            ItemDelegate {
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                text: modelData.product + (modelData.page === "web" ? "   " + qsTr("(opens in the browser for now)") : "")
                onClicked: backend.selectDevice(modelData.serial)
            }
        }

        Item { Layout.preferredHeight: 16 }
    }
}
