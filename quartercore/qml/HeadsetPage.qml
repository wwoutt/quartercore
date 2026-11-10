// Headset: lighting, equalizer, sidetone, mic LED, sleep, buttons and profiles
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Tested on the HS80 MAX WIRELESS. Like the web interface, the settings are
// only shown while the headset is switched on.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: page
    contentHeight: content.implicitHeight + 32
    clip: true
    ScrollBar.vertical: ScrollBar {}
    readonly property var hs: backend.active

    // Unsaved edits: equalizer band id -> value, zone id -> colour
    property var eq: ({})
    property var zones: ({})
    // OpenLinkHub keeps the default and the active profile
    readonly property var deletable: (hs.userProfiles || []).filter(p => p !== "default" && p !== hs.userProfile)

    function hex(c) {
        const h = v => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + h(c.r) + h(c.g) + h(c.b)
    }
    function edit(name, key, value) {
        const copy = Object.assign({}, page[name])
        copy[key] = value
        page[name] = copy
    }

    ColumnLayout {
        id: content
        x: 24
        y: 20
        width: page.width - 60
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            ColumnLayout {
                spacing: 0
                Label { text: hs.product || ""; font.pixelSize: 26 }
                Label {
                    text: hs.connected ? qsTr("Battery %1 %").arg(hs.battery || 0) : qsTr("Switched off")
                    opacity: 0.6
                }
            }
            Item { Layout.fillWidth: true }
            Label { text: qsTr("Profile"); visible: hs.connected }
            ComboBox {
                visible: hs.connected
                model: hs.userProfiles || []
                currentIndex: (hs.userProfiles || []).indexOf(hs.userProfile)
                onActivated: headset.setUserProfile(currentText)
            }
            Button { text: qsTr("Save as…"); visible: hs.connected; onClicked: saveProfile.open() }
            ToolButton {
                visible: hs.connected
                icon.name: "edit-delete"
                enabled: page.deletable.length > 0
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Delete a profile")
                onClicked: deleteProfile.open()
            }
            Button {
                text: qsTr("Open in browser")
                icon.name: "internet-web-browser"
                onClicked: backend.openInBrowser(hs.serial)
            }
        }

        Label {
            visible: !hs.connected
            Layout.fillWidth: true
            Layout.topMargin: 40
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            font.pixelSize: 16
            opacity: 0.8
            text: qsTr("The headset is switched off or out of range. Switch it on to change its settings.")
        }

        // Lighting
        Frame {
            visible: hs.connected
            Layout.fillWidth: true
            GridLayout {
                anchors.fill: parent
                columns: 4
                columnSpacing: 16
                rowSpacing: 10
                Label { text: qsTr("Lighting"); font.bold: true; Layout.columnSpan: 4 }

                Label { text: qsTr("Effect") }
                ComboBox {
                    Layout.fillWidth: true
                    model: hs.rgbModes || []
                    currentIndex: (hs.rgbModes || []).indexOf(hs.rgbMode)
                    onActivated: headset.setRgbMode(currentText)
                }
                Label { text: qsTr("Brightness") }
                RowLayout {
                    Layout.fillWidth: true
                    Slider {
                        id: brightness
                        Layout.fillWidth: true
                        from: 0; to: 100
                        value: hs.brightness || 0
                        onPressedChanged: if (!pressed) headset.setBrightness(Math.round(value))
                        Binding on value { when: !brightness.pressed; value: hs.brightness || 0 }
                    }
                    Label { text: Math.round(brightness.value) + " %"; Layout.preferredWidth: 45 }
                }

                Label {
                    text: qsTr("Zone colours")
                    visible: (hs.zones || []).length > 0
                    ToolTip.visible: zoneHover.hovered
                    ToolTip.text: qsTr("Used by the effect \"headset\".")
                    HoverHandler { id: zoneHover }
                }
                RowLayout {
                    Layout.columnSpan: 3
                    visible: (hs.zones || []).length > 0
                    spacing: 10
                    Repeater {
                        model: hs.zones || []
                        delegate: RowLayout {
                            spacing: 6
                            ColorButton {
                                value: page.zones[String(modelData.id)] || modelData.color
                                dialogTitle: modelData.name
                                onPicked: c => page.edit("zones", String(modelData.id), page.hex(c))
                            }
                            Label { text: modelData.name; Layout.rightMargin: 10 }
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: qsTr("Save")
                        icon.name: "document-save"
                        enabled: Object.keys(page.zones).length > 0
                        highlighted: enabled
                        onClicked: { headset.setZoneColors(page.zones); page.zones = ({}) }
                    }
                }
            }
        }

        // Sound
        Frame {
            visible: hs.connected
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 10
                RowLayout {
                    Label { text: qsTr("Equalizer"); font.bold: true; Layout.fillWidth: true }
                    Button {
                        text: qsTr("Flat")
                        ToolTip.visible: hovered
                        ToolTip.text: qsTr("All bands to 0 dB")
                        onClicked: {
                            const flat = {}
                            ;(hs.equalizer || []).forEach(b => flat[String(b.id)] = 0)
                            page.eq = flat
                        }
                    }
                    Button {
                        text: qsTr("Undo")
                        enabled: Object.keys(page.eq).length > 0
                        onClicked: page.eq = ({})
                    }
                    Button {
                        text: qsTr("Save")
                        icon.name: "document-save"
                        enabled: Object.keys(page.eq).length > 0
                        highlighted: enabled
                        onClicked: { headset.setEqualizer(page.eq); page.eq = ({}) }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    ColumnLayout {
                        Layout.preferredWidth: 50
                        Label { text: "+12 dB"; opacity: 0.6 }
                        Item { Layout.fillHeight: true }
                        Label { text: "0"; opacity: 0.6 }
                        Item { Layout.fillHeight: true }
                        Label { text: "-12 dB"; opacity: 0.6 }
                        Layout.preferredHeight: 170
                        Layout.topMargin: 20
                    }
                    Repeater {
                        model: hs.equalizer || []
                        delegate: ColumnLayout {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 56
                            spacing: 2
                            readonly property int current: page.eq[String(modelData.id)] !== undefined
                                                           ? page.eq[String(modelData.id)] : modelData.value
                            Label {
                                Layout.alignment: Qt.AlignHCenter
                                text: (current > 0 ? "+" : "") + current
                                font.bold: page.eq[String(modelData.id)] !== undefined
                            }
                            Slider {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredHeight: 170
                                orientation: Qt.Vertical
                                // No stepSize: the KDE style would draw tick marks; values are rounded
                                from: -12; to: 12
                                value: current
                                onMoved: page.edit("eq", String(modelData.id), Math.round(value))
                            }
                            Label {
                                Layout.alignment: Qt.AlignHCenter
                                text: modelData.name
                                opacity: 0.7
                            }
                        }
                    }
                }
            }
        }

        // Microphone, sidetone and sleep
        Frame {
            visible: hs.connected
            Layout.fillWidth: true
            GridLayout {
                anchors.fill: parent
                columns: 4
                columnSpacing: 16
                rowSpacing: 10

                Switch {
                    Layout.columnSpan: 2
                    visible: !!hs.hasSidetone
                    text: qsTr("Sidetone (hear your own voice)")
                    checked: !!hs.sidetone
                    onToggled: headset.setSidetone(checked)
                }
                RowLayout {
                    Layout.columnSpan: 2
                    visible: !!hs.hasSidetone
                    enabled: !!hs.sidetone
                    Slider {
                        id: sidetone
                        Layout.fillWidth: true
                        from: 1; to: 100
                        value: hs.sidetoneValue || 0
                        onPressedChanged: if (!pressed) headset.setSidetoneValue(Math.round(value))
                        Binding on value { when: !sidetone.pressed; value: hs.sidetoneValue || 0 }
                    }
                    Label { text: Math.round(sidetone.value) + " %"; Layout.preferredWidth: 45 }
                }

                Switch {
                    Layout.columnSpan: 2
                    visible: !!hs.hasMicLed
                    text: qsTr("Mic LED off while the mic is on")
                    checked: !!hs.micLedOff
                    onToggled: headset.setMicLedOff(checked)
                }
                Label { text: qsTr("Sleep after"); visible: (hs.sleepModes || []).length > 0 }
                ComboBox {
                    Layout.fillWidth: true
                    visible: (hs.sleepModes || []).length > 0
                    textRole: "label"
                    valueRole: "value"
                    model: (hs.sleepModes || []).map(o => ({ value: o.value, label: qsTr(o.name) }))
                    currentIndex: (hs.sleepModes || []).findIndex(o => o.value === hs.sleepMode)
                    onActivated: headset.setSleepMode(currentValue)
                }
            }
        }

        // Buttons
        Frame {
            visible: hs.connected && (hs.buttons || []).length > 0
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 8
                Label { text: qsTr("Buttons"); font.bold: true }
                Repeater {
                    model: hs.buttons || []
                    delegate: RowLayout {
                        id: button
                        Layout.fillWidth: true
                        spacing: 10
                        // Edited copy of the assignment; reset when the saved data changes
                        property var work: Object.assign({}, modelData)
                        readonly property var values: headset.buttonValues[String(work.type)] || []
                        readonly property bool changed: JSON.stringify(work) !== JSON.stringify(modelData)
                        function set(name, value) {
                            const copy = Object.assign({}, work)
                            copy[name] = value
                            work = copy
                        }

                        Label { text: modelData.name; font.bold: true; Layout.preferredWidth: 110 }
                        CheckBox {
                            text: qsTr("Default action")
                            checked: !!button.work.enabled
                            onToggled: button.set("enabled", checked)
                        }
                        CheckBox {
                            text: qsTr("Hold")
                            enabled: !button.work.enabled
                            checked: !!button.work.pressAndHold
                            onToggled: button.set("pressAndHold", checked)
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Keeps sending the action until the button is released.")
                        }
                        CheckBox {
                            text: qsTr("On release")
                            enabled: !button.work.enabled
                            checked: !!button.work.onRelease
                            onToggled: button.set("onRelease", checked)
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Runs the action when the button is released instead of pressed.")
                        }
                        ComboBox {
                            enabled: !button.work.enabled
                            textRole: "label"
                            valueRole: "value"
                            model: (hs.buttonTypes || []).map(o => ({ value: o.value, label: qsTr(o.name) }))
                            currentIndex: (hs.buttonTypes || []).findIndex(o => o.value === button.work.type)
                            onActivated: {
                                const list = headset.buttonValues[String(currentValue)] || []
                                button.work = Object.assign({}, button.work,
                                                            { type: currentValue, value: list.length > 0 ? list[0].value : 0 })
                            }
                        }
                        ComboBox {
                            Layout.fillWidth: true
                            visible: button.values.length > 0
                            enabled: !button.work.enabled
                            editable: button.values.length > 20
                            textRole: "name"
                            valueRole: "value"
                            model: button.values
                            currentIndex: button.values.findIndex(o => o.value === button.work.value)
                            onActivated: button.set("value", currentValue)
                            onAccepted: {
                                const i = find(editText, Qt.MatchContains)
                                if (i >= 0) { currentIndex = i; button.set("value", button.values[i].value) }
                            }
                        }
                        Item { Layout.fillWidth: true; visible: button.values.length === 0 }
                        Button {
                            text: qsTr("Save")
                            icon.name: "document-save"
                            enabled: button.changed
                            highlighted: enabled
                            onClicked: headset.setButton(modelData.keyId, button.work)
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: saveProfile
        anchors.centerIn: parent
        modal: true
        title: qsTr("Save profile as")
        standardButtons: Dialog.Ok | Dialog.Cancel
        onOpened: { profileName.text = ""; profileName.forceActiveFocus() }
        onAccepted: headset.saveUserProfile(profileName.text)
        TextField {
            id: profileName
            width: 260
            placeholderText: qsTr("At least 3 letters or digits")
            validator: RegularExpressionValidator { regularExpression: /[a-zA-Z0-9]*/ }
            onAccepted: saveProfile.accept()
        }
    }

    Dialog {
        id: deleteProfile
        anchors.centerIn: parent
        modal: true
        title: qsTr("Delete a profile")
        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: headset.deleteUserProfile(deleteChoice.currentText)
        ColumnLayout {
            ComboBox { id: deleteChoice; Layout.fillWidth: true; model: page.deletable }
            Label { text: qsTr("The default and the active profile can't be deleted.") }
        }
    }
}
