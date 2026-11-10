// Settings: connection, language, tray, autostart, about
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: page
    contentHeight: content.implicitHeight
    clip: true
    ScrollBar.vertical: ScrollBar {}

    ColumnLayout {
        id: content
        width: page.width - 12
        spacing: 12

        Label {
            text: qsTr("Settings")
            font.pixelSize: 26
            Layout.leftMargin: 24
            Layout.topMargin: 20
        }

        Frame {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24

            GridLayout {
                anchors.fill: parent
                columns: 2
                columnSpacing: 16
                rowSpacing: 10

                Label { text: qsTr("OpenLinkHub address") }
                RowLayout {
                    Layout.fillWidth: true
                    TextField {
                        id: url
                        Layout.fillWidth: true
                        text: settings.serverUrl
                        placeholderText: "http://127.0.0.1:27003"
                        onAccepted: apply.clicked()
                    }
                    Button {
                        id: apply
                        text: qsTr("Connect")
                        enabled: url.text.trim() !== "" && url.text.trim().replace(/\/$/, "") !== backend.serverUrl
                        onClicked: {
                            settings.serverUrl = url.text
                            backend.setServerUrl(settings.serverUrl)
                        }
                    }
                }

                Label { text: qsTr("Language") }
                ComboBox {
                    Layout.fillWidth: true
                    textRole: "label"
                    valueRole: "code"
                    model: languages.map(l => ({ code: l.code, label: l.code === "system" ? qsTr("System language") : l.name }))
                    Component.onCompleted: currentIndex = indexOfValue(settings.language)
                    onActivated: settings.language = currentValue
                }
            }
        }

        Frame {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24

            ColumnLayout {
                anchors.fill: parent
                spacing: 6

                Switch {
                    text: qsTr("Start Quartercore when I log in")
                    checked: settings.autostart
                    onToggled: settings.autostart = checked
                }
                Switch {
                    text: qsTr("When starting at login, show only the tray icon")
                    enabled: settings.autostart && trayAvailable
                    checked: settings.startMinimized
                    onToggled: settings.startMinimized = checked
                    Layout.leftMargin: 24
                }
                Switch {
                    text: qsTr("Keep running in the tray when the window is closed")
                    enabled: trayAvailable
                    checked: settings.closeToTray
                    onToggled: settings.closeToTray = checked
                }
                Label {
                    visible: !trayAvailable
                    text: qsTr("No system tray found on this desktop, so these options are off.")
                    opacity: 0.7
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }
            }
        }

        Label {
            text: qsTr("About")
            font.pixelSize: 18
            Layout.leftMargin: 24
            Layout.topMargin: 8
        }

        Frame {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24

            ColumnLayout {
                anchors.fill: parent
                spacing: 6

                Label { text: "Quartercore " + appVersion; font.bold: true }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    textFormat: Text.StyledText
                    onLinkActivated: link => Qt.openUrlExternally(link)
                    text: qsTr("Built on <a href=\"https://github.com/jurkovic-nikola/OpenLinkHub\">OpenLinkHub</a> by Nikola Jurković, who made the device support and the API.")
                          + "<br>" + qsTr("Written by Claude (Anthropic) for wwoutt.")
                          + "<br>" + qsTr("Not an official Corsair product. Corsair, iCUE and XENEON are trademarks of Corsair.")
                          + "<br>" + qsTr("License: GPL-3.0 or later.") + " <a href=\"https://github.com/wwoutt/quartercore\">github.com/wwoutt/quartercore</a>"
                }
            }
        }

        Item { Layout.preferredHeight: 16 }
    }
}
