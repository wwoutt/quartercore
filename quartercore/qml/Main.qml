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
    // Shown from Python, so it can start in the tray only
    visible: false
    title: "Quartercore"

    // "" for the overview and device pages, or "profiles" or "settings"
    property string section: ""

    function open(serial) {
        section = ""
        backend.selectDevice(serial)
    }

    // Closing keeps Quartercore in the tray when that is enabled
    onClosing: close => {
        if (trayAvailable && settings.closeToTray) {
            close.accepted = false
            window.hide()
        }
    }

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
                    text: qsTr("Overview")
                    icon.name: "view-dashboard"
                    highlighted: window.section === "" && backend.activeSerial === ""
                    onClicked: window.open("")
                }

                ItemDelegate {
                    Layout.fillWidth: true
                    text: qsTr("Temperature profiles")
                    icon.name: "temperature-normal"
                    highlighted: window.section === "profiles"
                    onClicked: window.section = "profiles"
                }

                Label {
                    text: qsTr("Devices")
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
                        highlighted: window.section === "" && backend.activeSerial === modelData.serial
                        onClicked: window.open(modelData.serial)
                    }
                }

                ItemDelegate {
                    Layout.fillWidth: true
                    text: qsTr("XENEON EDGE layout")
                    icon.name: "video-display"
                    onClicked: backend.openXeneonEditor()
                }

                ItemDelegate {
                    Layout.fillWidth: true
                    text: qsTr("Settings")
                    icon.name: "configure"
                    highlighted: window.section === "settings"
                    onClicked: window.section = "settings"
                }

                Label {
                    text: (backend.connected ? qsTr("Connected") : qsTr("Not connected")) + " · v" + appVersion
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
                source: window.section === "settings" ? "SettingsPage.qml"
                      : !backend.connected ? "Disconnected.qml"
                      : window.section === "profiles" ? "ProfilesPage.qml"
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
        // Opening a device from the tray menu leaves the other sections
        function onActiveChanged() {
            if (backend.activeSerial !== "")
                window.section = ""
        }
    }
}
