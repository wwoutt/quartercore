// Keyboard: key colours, key assignments, macros and the keyboard settings
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Colours tab: click keys to select them, pick a colour and apply it.
// Key assignments tab: click one key to change what it does.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Flickable {
    id: page
    contentHeight: content.implicitHeight + 32
    clip: true
    ScrollBar.vertical: ScrollBar {}
    readonly property var kb: backend.active

    // keyId -> true for the selected keys; survives the refresh every two seconds
    property var selected: ({})
    readonly property var selectedIds: Object.keys(selected).map(Number)
    property color pending: "#00ffff"
    // The key whose assignment is edited (key assignments tab), -1 for none
    property int assignKey: -1
    readonly property bool assigning: tabs.currentIndex === 1

    // Updated in place, so the drawing doesn't flicker on every refresh
    ListModel { id: keys }

    function syncKeys() {
        const list = kb.keys || []
        const item = k => ({ keyId: k.keyId, keyRow: k.row, label: k.name, kx: k.x, ky: k.y, kw: k.w, kh: k.h,
                             tint: k.color, light: k.light, noColor: k.noColor,
                             custom: !!k.assignment && !k.assignment.enabled && k.assignment.type !== 0 })
        if (list.length !== keys.count) {
            keys.clear()
            list.forEach(k => keys.append(item(k)))
            selected = ({})
            return
        }
        list.forEach((k, i) => keys.set(i, item(k)))
    }
    function toggle(id) {
        const copy = Object.assign({}, selected)
        if (copy[id]) delete copy[id]; else copy[id] = true
        selected = copy
    }
    function select(test) {
        const copy = {}
        for (let i = 0; i < keys.count; i++) {
            const k = keys.get(i)
            if (!k.noColor && test(k)) copy[k.keyId] = true
        }
        selected = copy
    }
    function selectRows() {
        const rows = {}
        for (let i = 0; i < keys.count; i++)
            if (selected[keys.get(i).keyId]) rows[keys.get(i).keyRow] = true
        select(k => rows[k.keyRow] === true)
    }
    function hex(c) {
        const h = v => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + h(c.r) + h(c.g) + h(c.b)
    }

    function keyData(id) {
        return (kb.keys || []).find(k => k.keyId === id) || null
    }

    Component.onCompleted: syncKeys()
    Connections {
        target: backend
        function onActiveChanged() { page.syncKeys() }
    }
    Connections {
        target: keyboard
        function onTabRequested(tab, keyId) {
            tabs.currentIndex = ["colours", "keys", "macros", "settings"].indexOf(tab)
            if (keyId >= 0) page.assignKey = keyId
        }
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
                Label { text: kb.product || ""; font.pixelSize: 26 }
                Label { text: qsTr("Firmware %1").arg(kb.firmware || "–"); opacity: 0.6 }
            }
            Item { Layout.fillWidth: true }
            Button {
                text: qsTr("Open in browser")
                icon.name: "internet-web-browser"
                onClicked: backend.openInBrowser(kb.serial)
            }
        }

        // The keyboard
        Item {
            id: board
            Layout.fillWidth: true
            // Fills the width, but never taller than 320 pixels (then centred)
            readonly property real scale: Math.min(width / Math.max(1, kb.keysWidth || 1),
                                                   320 / Math.max(1, kb.keysHeight || 1))
            readonly property real offset: Math.max(0, (width - (kb.keysWidth || 0) * scale) / 2)
            Layout.preferredHeight: (kb.keysHeight || 0) * scale

            Repeater {
                model: keys
                delegate: Rectangle {
                    readonly property bool isSelected: page.assigning ? page.assignKey === model.keyId
                                                                      : page.selected[model.keyId] === true
                    x: board.offset + model.kx * board.scale
                    y: model.ky * board.scale
                    width: model.kw * board.scale - 1
                    height: model.kh * board.scale - 1
                    radius: model.light ? 2 : 4
                    color: model.light ? model.tint : "#2a2d33"
                    opacity: model.noColor ? 0.45 : 1
                    border.width: isSelected ? 2 : 1
                    border.color: isSelected ? "white" : Qt.rgba(1, 1, 1, 0.12)

                    Label {
                        anchors.centerIn: parent
                        width: parent.width - 4
                        horizontalAlignment: Text.AlignHCenter
                        text: model.label
                        // Dark text on a filled light zone, the key colour on a key
                        color: model.noColor ? "#a1a1a1" : model.light ? "#101114" : model.tint
                        font.pixelSize: Math.max(7, 15 * board.scale)
                        font.bold: true
                        elide: Text.ElideRight
                        visible: !model.light || model.label !== ""
                    }
                    // A key with its own assignment gets a dot in the corner
                    Rectangle {
                        visible: model.custom
                        width: Math.max(4, 8 * board.scale)
                        height: width
                        radius: width / 2
                        color: "#3daee9"
                        anchors { top: parent.top; right: parent.right; margins: 3 }
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: page.assigning ? !model.light : !model.noColor
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (page.assigning) page.assignKey = model.keyId
                            else page.toggle(model.keyId)
                        }
                    }
                }
            }
        }

        TabBar {
            id: tabs
            Layout.fillWidth: true
            TabButton { text: qsTr("Colours") }
            TabButton { text: qsTr("Key assignments") }
            TabButton { text: qsTr("Macros") }
            TabButton { text: qsTr("Settings") }
        }

        StackLayout {
            id: stack
            Layout.fillWidth: true
            currentIndex: tabs.currentIndex
            // Only as tall as the open tab
            Layout.preferredHeight: stack.children[currentIndex] ? stack.children[currentIndex].implicitHeight : 0

            ColumnLayout {
                spacing: 14
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    visible: (kb.rgbMode || "") !== "keyboard"
                    text: qsTr("The keyboard now shows the effect \"%1\". Key colours are visible with the effect \"keyboard\".").arg(kb.rgbMode || "")
                    opacity: 0.8
                }

                // Colour for the selected keys
                Frame {
                    Layout.fillWidth: true
                    RowLayout {
                        anchors.fill: parent
                        spacing: 10
                        Label { text: qsTr("Select") }
                        Button { text: qsTr("All"); onClicked: page.select(k => true) }
                        Button { text: qsTr("Rows"); enabled: page.selectedIds.length > 0; onClicked: page.selectRows() }
                        Button { text: qsTr("Lights only"); onClicked: page.select(k => k.light) }
                        Button { text: qsTr("None"); enabled: page.selectedIds.length > 0; onClicked: page.selected = ({}) }
                        Item { Layout.fillWidth: true }
                        ColorButton {
                            value: page.pending
                            onPicked: c => page.pending = c
                        }
                        Button {
                            text: qsTr("Apply to %1 keys").arg(page.selectedIds.length)
                            icon.name: "color-fill"
                            enabled: page.selectedIds.length > 0
                            highlighted: enabled
                            onClicked: backend.setKeyColors(page.selectedIds, page.hex(page.pending))
                        }
                    }
                }

                // Colour profiles
                Frame {
                    Layout.fillWidth: true
                    RowLayout {
                        anchors.fill: parent
                        spacing: 10
                        ColumnLayout {
                            spacing: 2
                            Layout.fillWidth: true
                            Label { text: qsTr("Colour profile"); font.bold: true }
                            Label {
                                text: qsTr("Colours apply right away. Save the profile to keep them after a restart.")
                                wrapMode: Text.WordWrap
                                opacity: 0.7
                                Layout.fillWidth: true
                            }
                        }
                        ComboBox {
                            Layout.preferredWidth: 160
                            model: kb.colorProfiles || []
                            currentIndex: (kb.colorProfiles || []).indexOf(kb.colorProfile)
                            onActivated: backend.setKeyboardColorProfile(currentText)
                        }
                        Button { text: qsTr("Save"); icon.name: "document-save"; onClicked: backend.saveKeyboardColorProfile() }
                        Button { text: qsTr("Save as…"); onClicked: saveAs.open() }
                        Button {
                            text: qsTr("Delete")
                            icon.name: "edit-delete"
                            enabled: (kb.colorProfile || "default") !== "default"
                            onClicked: deleteProfile.open()
                        }
                    }
                }
            }

            KeyAssignmentPanel {
                keyId: page.assignKey
                key: page.keyData(page.assignKey)
            }

            MacroPanel {}

            ColumnLayout {
                spacing: 14
                // Settings
                Frame {
                    Layout.fillWidth: true
                    GridLayout {
                        anchors.fill: parent
                        columns: 4
                        columnSpacing: 16
                        rowSpacing: 8

                        Label { text: qsTr("Effect") }
                        ComboBox {
                            Layout.fillWidth: true
                            model: kb.rgbModes || []
                            currentIndex: (kb.rgbModes || []).indexOf(kb.rgbMode)
                            onActivated: backend.setKeyboardRgbMode(currentText)
                        }
                        Label { text: qsTr("Device profile"); visible: (kb.userProfiles || []).length > 1 }
                        ComboBox {
                            Layout.fillWidth: true
                            visible: (kb.userProfiles || []).length > 1
                            model: kb.userProfiles || []
                            currentIndex: (kb.userProfiles || []).indexOf(kb.userProfile)
                            onActivated: backend.setUserProfile(currentText)
                        }

                        Label { text: qsTr("Layout"); visible: (kb.layouts || []).length > 0 }
                        ComboBox {
                            Layout.fillWidth: true
                            visible: (kb.layouts || []).length > 0
                            model: kb.layouts || []
                            currentIndex: (kb.layouts || []).indexOf(kb.layout)
                            onActivated: backend.setKeyboardLayout(currentText)
                        }
                        Label { text: qsTr("Polling rate"); visible: (kb.pollingRates || []).length > 0 }
                        ComboBox {
                            Layout.fillWidth: true
                            visible: (kb.pollingRates || []).length > 0
                            textRole: "name"
                            valueRole: "value"
                            model: kb.pollingRates || []
                            currentIndex: (kb.pollingRates || []).findIndex(o => o.value === kb.pollingRate)
                            onActivated: backend.setKeyboardPollingRate(currentValue)
                        }

                        Label { text: qsTr("Control dial"); visible: (kb.dialOptions || []).length > 0 }
                        ComboBox {
                            Layout.fillWidth: true
                            visible: (kb.dialOptions || []).length > 0
                            textRole: "name"
                            valueRole: "value"
                            model: kb.dialOptions || []
                            currentIndex: (kb.dialOptions || []).findIndex(o => o.value === kb.dial)
                            onActivated: backend.setKeyboardDial(currentValue)
                        }
                        Label { text: qsTr("Debounce time"); visible: (kb.debounceTimes || []).length > 0 }
                        ComboBox {
                            Layout.fillWidth: true
                            visible: (kb.debounceTimes || []).length > 0
                            textRole: "name"
                            valueRole: "value"
                            model: kb.debounceTimes || []
                            currentIndex: (kb.debounceTimes || []).findIndex(o => o.value === kb.debounceTime)
                            onActivated: backend.setKeyboardDebounceTime(currentValue)
                        }
                    }
                }

                KeyboardExtrasPanel {
                    Layout.fillWidth: true
                    hasDial: (kb.dialOptions || []).length > 0
                }
            }
        }
    }

    Dialog {
        id: saveAs
        anchors.centerIn: parent
        modal: true
        title: qsTr("Save colour profile as")
        standardButtons: Dialog.Ok | Dialog.Cancel
        onOpened: { profileName.text = ""; profileName.forceActiveFocus() }
        onAccepted: backend.saveKeyboardColorProfileAs(profileName.text)
        TextField {
            id: profileName
            width: 260
            placeholderText: qsTr("Letters and digits, e.g. Gaming")
            validator: RegularExpressionValidator { regularExpression: /[a-zA-Z0-9]*/ }
            onAccepted: saveAs.accept()
        }
    }

    Dialog {
        id: deleteProfile
        anchors.centerIn: parent
        modal: true
        title: qsTr("Delete profile %1?").arg(kb.colorProfile || "")
        standardButtons: Dialog.Yes | Dialog.No
        Label { text: qsTr("The keyboard goes back to the default colour profile.") }
        onAccepted: backend.deleteKeyboardColorProfile(kb.colorProfile)
    }
}
