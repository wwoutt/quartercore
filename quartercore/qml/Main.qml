// Main window: device list on the left, the selected page on the right
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1200
    height: 760
    minimumWidth: 760
    minimumHeight: 480
    visible: true
    title: "Quartercore"

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Sidebar
        Pane {
            Layout.fillHeight: true
            Layout.preferredWidth: 250
            padding: 0

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Label {
                    text: "Quartercore"
                    font.pixelSize: 20
                    font.bold: true
                    Layout.margins: 16
                }

                ItemDelegate {
                    Layout.fillWidth: true
                    text: "Overview"
                    icon.name: "view-dashboard"
                    highlighted: backend.activeSerial === ""
                    onClicked: backend.selectDevice("")
                }

                Label {
                    text: "Devices"
                    opacity: 0.6
                    Layout.leftMargin: 16
                    Layout.topMargin: 12
                    Layout.bottomMargin: 4
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: backend.devices
                    delegate: ItemDelegate {
                        width: ListView.view.width
                        text: modelData.product
                        icon.name: modelData.page === "web" ? "internet-web-browser" : "preferences-system"
                        highlighted: backend.activeSerial === modelData.serial
                        onClicked: backend.selectDevice(modelData.serial)
                    }
                }

                ItemDelegate {
                    Layout.fillWidth: true
                    text: "XENEON EDGE layout"
                    icon.name: "video-display"
                    onClicked: backend.openXeneonEditor()
                }

                Label {
                    text: (backend.connected ? "Connected" : "Not connected") + " · v" + appVersion
                    opacity: 0.6
                    font.pixelSize: 12
                    Layout.margins: 16
                }
            }
        }

        ToolSeparator {
            Layout.fillHeight: true
            orientation: Qt.Vertical
            padding: 0
        }

        // Page
        Pane {
            Layout.fillWidth: true
            Layout.fillHeight: true
            padding: 0

            Loader {
                anchors.fill: parent
                source: !backend.connected ? "Disconnected.qml"
                      : backend.activeSerial === "" ? "Overview.qml"
                      : backend.active.page === "linkhub" ? "LinkHub.qml"
                      : backend.active.page === "web" ? "WebOnly.qml"
                      : "Loading.qml"
            }
        }
    }

    // Short feedback after a change
    ToolTip {
        id: toast
        x: (window.width - width) / 2
        y: window.height - height - 24
        timeout: 2500
    }

    Connections {
        target: backend
        function onNotify(text, ok) {
            toast.text = (ok ? "✓ " : "⚠ ") + text
            toast.open()
        }
    }
}
