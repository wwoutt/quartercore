// iCUE LINK System Hub: fans, pump, speed profiles, RGB and labels
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
    readonly property var hub: backend.active

    // Updated in place, so open menus and labels being edited survive the
    // refresh every two seconds
    ListModel { id: channels }

    function syncChannels() {
        const list = hub.channels || []
        if (list.length !== channels.count) {
            channels.clear()
            list.forEach(ch => channels.append(ch))
            return
        }
        list.forEach((ch, i) => channels.set(i, ch))
    }

    Component.onCompleted: syncChannels()
    Connections {
        target: backend
        function onActiveChanged() { page.syncChannels() }
    }

    ColumnLayout {
        id: content
        width: page.availableWidth
        spacing: 12

        RowLayout {
            Layout.leftMargin: 24
            Layout.rightMargin: 24
            Layout.topMargin: 20

            ColumnLayout {
                spacing: 0
                Label { text: hub.product || ""; font.pixelSize: 26 }
                Label { text: "Firmware " + (hub.firmware || "–"); opacity: 0.6 }
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "Open in browser"
                icon.name: "internet-web-browser"
                onClicked: backend.openInBrowser(hub.serial)
            }
        }

        // Settings for the whole hub
        Frame {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24

            GridLayout {
                anchors.fill: parent
                columns: 3
                columnSpacing: 16
                rowSpacing: 8

                Label { text: "Brightness" }
                Slider {
                    id: brightness
                    Layout.fillWidth: true
                    // No stepSize: the KDE style would draw 100 tick marks
                    from: 0; to: 100
                    value: hub.brightness || 0
                    onPressedChanged: if (!pressed) backend.setBrightness(Math.round(value))
                    Binding on value { when: !brightness.pressed; value: hub.brightness || 0 }
                }
                Label { text: Math.round(brightness.value) + " %"; Layout.preferredWidth: 50 }

                Label { text: "All fans and pump" }
                ComboBox {
                    Layout.fillWidth: true
                    model: ["Choose a speed profile…"].concat(backend.speedProfiles)
                    onActivated: index => { if (index > 0) backend.setAllSpeedProfiles(currentText); currentIndex = 0 }
                }
                Item {}

                Label { text: "All lighting" }
                ComboBox {
                    Layout.fillWidth: true
                    model: ["Choose an RGB profile…"].concat(hub.rgbModes || [])
                    onActivated: index => { if (index > 0) backend.setAllRgbProfiles(currentText); currentIndex = 0 }
                }
                Item {}
            }
        }

        Label {
            text: channels.count + " connected devices"
            font.pixelSize: 18
            Layout.leftMargin: 24
            Layout.topMargin: 8
        }

        Repeater {
            model: channels
            delegate: ChannelRow {
                Layout.fillWidth: true
                Layout.leftMargin: 24
                Layout.rightMargin: 24
                rgbModes: hub.rgbModes || []
            }
        }

        Item { Layout.preferredHeight: 16 }
    }
}
