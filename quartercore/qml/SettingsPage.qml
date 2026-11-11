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


        // Home Assistant for the XENEON EDGE widgets
        Frame {
            Layout.fillWidth: true
            Layout.leftMargin: 24
            Layout.rightMargin: 24

            GridLayout {
                anchors.fill: parent
                columns: 2
                columnSpacing: 16
                rowSpacing: 10

                Label { text: qsTr("Home Assistant"); font.bold: true; Layout.columnSpan: 2 }
                Label { text: qsTr("Address") }
                TextField {
                    id: haUrl
                    Layout.fillWidth: true
                    text: settings.haUrl
                    placeholderText: "http://homeassistant.local:8123"
                    onEditingFinished: settings.haUrl = text
                }
                Label { text: qsTr("Token") }
                TextField {
                    id: haToken
                    Layout.fillWidth: true
                    text: settings.haToken
                    echoMode: TextInput.Password
                    placeholderText: qsTr("Long-lived access token")
                    onEditingFinished: settings.haToken = text
                }
                Item {}
                RowLayout {
                    Layout.fillWidth: true
                    Button {
                        text: qsTr("Test the connection")
                        onClicked: {
                            settings.haUrl = haUrl.text
                            settings.haToken = haToken.text
                            homeAssistant.test()
                        }
                    }
                    Label {
                        text: homeAssistant.testResult
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        opacity: 0.8
                    }
                }
                Item {}
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.6
                    text: qsTr("Make the token in Home Assistant under your profile, Security, Long-lived access tokens. Quartercore keeps it in its settings file, readable only by you, and only sends it to this address.")
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
            text: qsTr("XENEON EDGE")
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

                Switch {
                    text: qsTr("Show the native kiosk fullscreen on the XENEON EDGE")
                    checked: settings.edgeKiosk
                    onToggled: settings.edgeKiosk = checked
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.7
                    text: (edge.screenName ? qsTr("Screen: %1.").arg(edge.screenName)
                                           : qsTr("No 2560 × 720 screen found."))
                          + " " + qsTr("It uses the layout of the XENEON EDGE layout editor. Turn off the web kiosk of the fork first (systemctl --user disable --now openlinkhub-xeneon-kiosk), so the two don't overlap.")
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
