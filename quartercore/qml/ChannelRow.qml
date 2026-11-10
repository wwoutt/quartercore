// One fan, pump or other device on the LINK System Hub
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// The role names (channelId, name, label, ...) come from the ListModel in
// LinkHub.qml, which mirrors backend.active.channels.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
    id: row
    property var rgbModes: []

    RowLayout {
        anchors.fill: parent
        spacing: 16

        ColumnLayout {
            Layout.preferredWidth: 220
            spacing: 2

            TextField {
                id: labelField
                Layout.fillWidth: true
                placeholderText: name
                font.bold: true
                // Keep what the user types while editing
                Binding on text { when: !labelField.activeFocus; value: label }
                onEditingFinished: {
                    if (text.trim() !== label && text.trim() !== "")
                        backend.setLabel(channelId, text)
                }
            }
            Label {
                text: (label !== "" ? name + " · " : "") + kind + " · channel " + channelId
                opacity: 0.6
                font.pixelSize: 12
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }

        ColumnLayout {
            Layout.preferredWidth: 110
            spacing: 0
            Label {
                text: hasSpeed ? rpm + " RPM" : "–"
                font.pixelSize: 20
                font.bold: true
            }
            Label {
                text: temperature
                visible: temperature !== ""
                opacity: 0.7
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Label { text: "Speed profile"; opacity: 0.6; font.pixelSize: 12 }
            ComboBox {
                Layout.fillWidth: true
                enabled: hasSpeed
                model: backend.speedProfiles
                currentIndex: backend.speedProfiles.indexOf(speedProfile)
                onActivated: backend.setSpeedProfile(channelId, currentText)
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Label { text: "RGB profile"; opacity: 0.6; font.pixelSize: 12 }
            ComboBox {
                Layout.fillWidth: true
                enabled: !isProbe
                model: row.rgbModes
                currentIndex: row.rgbModes.indexOf(rgbProfile)
                onActivated: backend.setRgbProfile(channelId, currentText)
            }
        }
    }
}
