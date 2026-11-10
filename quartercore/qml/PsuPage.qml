// Power supply: power, voltage rails, temperatures and the fan mode
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: page
    contentHeight: content.implicitHeight + 32
    clip: true
    ScrollBar.vertical: ScrollBar {}
    readonly property var psu: backend.active
    readonly property real availableWidth: width - 12

    function watts(v) { return v.toFixed(v < 10 ? 1 : 0) + " W" }

    ColumnLayout {
        id: content
        x: 24
        y: 20
        width: page.availableWidth - 48
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 0
                Label { text: psu.product || ""; font.pixelSize: 26 }
                Label {
                    text: qsTr("Input voltage %1 V").arg(psu.inputVoltage || 0)
                    opacity: 0.6
                    visible: (psu.inputVoltage || 0) > 0
                }
            }
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("Open in browser")
                icon.name: "internet-web-browser"
                onClicked: backend.openInBrowser(psu.serial)
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: Math.max(1, Math.floor(content.width / 220))
            columnSpacing: 12
            rowSpacing: 12

            StatCard { title: qsTr("Power"); value: page.watts(psu.power || 0) }
            StatCard {
                title: qsTr("Output power")
                value: page.watts(psu.outputPower || 0)
                visible: (psu.outputPower || 0) > 0
            }
            Repeater {
                model: psu.temperatures || []
                StatCard { title: modelData.name; value: modelData.value }
            }
            Repeater {
                model: psu.fans || []
                StatCard {
                    title: modelData.name
                    value: modelData.rpm + " RPM"
                    detail: modelData.rpm === 0 ? qsTr("stopped, the fan starts when needed") : ""
                }
            }
        }

        Frame {
            Layout.fillWidth: true
            visible: (psu.rails || []).length > 0

            GridLayout {
                anchors.fill: parent
                columns: 4
                columnSpacing: 24
                rowSpacing: 6

                Label { text: qsTr("Rail"); opacity: 0.6 }
                Label { text: qsTr("Voltage"); opacity: 0.6 }
                Label { text: qsTr("Current"); opacity: 0.6 }
                Label { text: qsTr("Power"); opacity: 0.6; Layout.fillWidth: true }

                Repeater {
                    model: psu.rails || []
                    delegate: Label { text: modelData.name; font.bold: true; Layout.row: index + 1; Layout.column: 0 }
                }
                Repeater {
                    model: psu.rails || []
                    delegate: Label { text: modelData.volts.toFixed(2) + " V"; Layout.row: index + 1; Layout.column: 1 }
                }
                Repeater {
                    model: psu.rails || []
                    delegate: Label { text: modelData.amps.toFixed(2) + " A"; Layout.row: index + 1; Layout.column: 2 }
                }
                Repeater {
                    model: psu.rails || []
                    delegate: Label { text: page.watts(modelData.watts); Layout.row: index + 1; Layout.column: 3 }
                }
            }
        }

        Frame {
            Layout.fillWidth: true

            RowLayout {
                anchors.fill: parent
                spacing: 16
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Label { text: qsTr("Fan mode"); font.bold: true }
                    Label {
                        text: qsTr("Default lets the power supply control its fan. A percentage keeps the fan at that speed.")
                        wrapMode: Text.WordWrap
                        opacity: 0.7
                        Layout.fillWidth: true
                    }
                }
                ComboBox {
                    id: fanMode
                    Layout.preferredWidth: 180
                    textRole: "name"
                    valueRole: "value"
                    model: psu.fanModes || []
                    currentIndex: (psu.fanModes || []).findIndex(m => m.value === psu.fanMode)
                    onActivated: backend.setPsuFanMode(currentValue)
                }
            }
        }
    }
}
