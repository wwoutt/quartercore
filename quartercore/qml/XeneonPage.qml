// XENEON EDGE screen: brightness, contrast, backlight and colour tones
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// The settings of OpenLinkHub's page xeneonedge.html; the layout of the
// widgets is on the "XENEON EDGE layout" page.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: page
    contentHeight: content.implicitHeight + 32
    clip: true
    ScrollBar.vertical: ScrollBar {}
    readonly property var xe: backend.active

    // A slider that sends its value when it is let go, and follows the device otherwise
    component Setting: RowLayout {
        id: setting
        property string label
        property int value
        property int to: 100
        property string suffix: " %"
        signal released(int value)
        Layout.fillWidth: true
        spacing: 12
        Label { text: setting.label; Layout.preferredWidth: 170 }
        Slider {
            id: slider
            Layout.fillWidth: true
            from: 0; to: setting.to
            value: setting.value
            onPressedChanged: if (!pressed) setting.released(Math.round(value))
            Binding on value { when: !slider.pressed; value: setting.value }
        }
        Label { text: Math.round(slider.value) + setting.suffix; Layout.preferredWidth: 60 }
    }

    ColumnLayout {
        id: content
        x: 24
        y: 20
        width: page.width - 60
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 0
                Label { text: xe.product || ""; font.pixelSize: 26 }
                Label {
                    text: xe.drivenBy === "quartercore-core" ? qsTr("Driven by quartercore-core") : qsTr("Driven by OpenLinkHub")
                    opacity: 0.6
                }
            }
            Item { Layout.fillWidth: true }
            Label { text: qsTr("Profile"); visible: (xe.userProfiles || []).length > 1 }
            ComboBox {
                visible: (xe.userProfiles || []).length > 1
                model: xe.userProfiles || []
                currentIndex: (xe.userProfiles || []).indexOf(xe.userProfile)
                onActivated: backend.setUserProfile(currentText)
            }
            Button {
                text: qsTr("XENEON EDGE layout")
                icon.name: "video-display"
                onClicked: window.section = "edge"
            }
        }

        Frame {
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                Label { text: qsTr("Screen"); font.bold: true }
                Setting {
                    label: qsTr("Brightness")
                    value: xe.brightness || 0
                    onReleased: v => backend.setXeneonValue("brightness", v)
                }
                Setting {
                    label: qsTr("Contrast")
                    value: xe.contrast || 0
                    onReleased: v => backend.setXeneonValue("contrast", v)
                }
                Setting {
                    label: qsTr("Backlight")
                    value: xe.backlight || 0
                    onReleased: v => backend.setXeneonValue("backlight", v)
                }
            }
        }

        Frame {
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                RowLayout {
                    Label { text: qsTr("Colour tone"); font.bold: true; Layout.fillWidth: true }
                    Button {
                        text: qsTr("Reset all settings")
                        icon.name: "edit-undo"
                        onClicked: resetDialog.open()
                    }
                }
                Repeater {
                    model: [qsTr("Red"), qsTr("Green"), qsTr("Blue")]
                    delegate: Setting {
                        required property int index
                        required property string modelData
                        label: modelData
                        to: 255
                        suffix: ""
                        value: (xe.tones || [0, 0, 0])[index]
                        onReleased: v => backend.setXeneonTone(index, v)
                    }
                }
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.6
                    text: qsTr("The factory values are red 150, green 126 and blue 140.")
                }
            }
        }
    }

    Dialog {
        id: resetDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("Reset the XENEON EDGE?")
        standardButtons: Dialog.Yes | Dialog.No
        Label { text: qsTr("Brightness and contrast go to 50 %, the backlight to 100 % and the colour tones to the factory values.") }
        onAccepted: backend.resetXeneon()
    }
}
