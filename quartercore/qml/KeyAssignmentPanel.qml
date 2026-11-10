// Key assignment of one keyboard key
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// The fields of the "Key assignments" window of the OpenLinkHub web interface
// (keyboards with a modifier key, like the K100).

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: panel
    property int keyId: -1
    property var key: null
    spacing: 12

    // The edited assignment; reset when another key is chosen
    property var work: ({})
    readonly property var values: keyboard.assignmentValues[String(work.type)] || []
    readonly property bool textValue: [2, 4, 8, 21].indexOf(work.type) >= 0
    // Keyboards without modifier keys (like the wired K100) ignore the modifier and "retain original"
    readonly property bool hasModifiers: keyboard.modifiers.length > 1

    function reset() {
        work = key && key.assignment ? Object.assign({}, key.assignment) : ({})
        if (work.type !== undefined && panel.textValue) work.value = work.valueString
    }
    function set(name, value) {
        const copy = Object.assign({}, work)
        copy[name] = value
        work = copy
    }
    onKeyIdChanged: reset()
    // The key data comes back every two seconds; only reset when nothing was changed
    onKeyChanged: if (!changed) reset()
    readonly property bool changed: !!key && !!key.assignment && JSON.stringify(work) !== JSON.stringify(
        Object.assign({}, key.assignment, panel.textValue ? { value: key.assignment.valueString } : {}))

    Label {
        visible: !panel.key
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        opacity: 0.8
        text: qsTr("Click a key on the keyboard above to change what it does. A dot marks keys with their own assignment.")
    }

    Frame {
        visible: !!panel.key
        Layout.fillWidth: true

        GridLayout {
            anchors.fill: parent
            columns: 4
            columnSpacing: 16
            rowSpacing: 10

            Label {
                Layout.columnSpan: 4
                text: qsTr("Key %1").arg(panel.key ? panel.key.name || "#" + panel.keyId : "")
                font.bold: true
                font.pixelSize: 18
            }

            CheckBox {
                Layout.columnSpan: 4
                text: qsTr("Default action")
                checked: !!panel.work.enabled
                onToggled: panel.set("enabled", checked)
                ToolTip.visible: hovered
                ToolTip.text: qsTr("The key does what it normally does and ignores the assignment below.")
            }

            Label { text: qsTr("Type") }
            ComboBox {
                Layout.fillWidth: true
                enabled: !panel.work.enabled
                textRole: "name"
                valueRole: "value"
                model: keyboard.assignmentTypes
                currentIndex: keyboard.assignmentTypes.findIndex(o => o.value === panel.work.type)
                onActivated: {
                    const copy = Object.assign({}, panel.work, { type: currentValue })
                    const list = keyboard.assignmentValues[String(currentValue)] || []
                    copy.value = list.length > 0 ? list[0].value : ([2, 4, 8, 21].indexOf(currentValue) >= 0 ? "" : 0)
                    panel.work = copy
                }
            }
            Label { text: qsTr("Value"); visible: panel.values.length > 0 }
            ComboBox {
                id: valueBox
                Layout.fillWidth: true
                visible: panel.values.length > 0
                enabled: !panel.work.enabled
                editable: panel.values.length > 20
                textRole: "name"
                valueRole: "value"
                model: panel.values
                currentIndex: panel.values.findIndex(o => o.value === panel.work.value)
                onActivated: panel.set("value", currentValue)
                onAccepted: {
                    const i = find(editText, Qt.MatchContains)
                    if (i >= 0) { currentIndex = i; panel.set("value", panel.values[i].value) }
                }
            }
            Item { visible: panel.values.length === 0; Layout.columnSpan: 2 }

            Label { text: qsTr("Modifier"); visible: panel.hasModifiers }
            ComboBox {
                Layout.fillWidth: true
                visible: panel.hasModifiers
                enabled: !panel.work.enabled
                textRole: "name"
                valueRole: "value"
                model: keyboard.modifiers
                currentIndex: keyboard.modifiers.findIndex(o => o.value === panel.work.modifier)
                onActivated: panel.set("modifier", currentValue)
            }
            Item { visible: !panel.hasModifiers; Layout.columnSpan: 2 }
            Label { text: qsTr("Toggle delay (ms)") }
            SpinBox {
                enabled: !panel.work.enabled
                from: 0
                to: 10000
                stepSize: 10
                editable: true
                value: panel.work.toggleDelay || 0
                onValueModified: panel.set("toggleDelay", value)
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Only for mouse assignments: the repeat waits this long. OpenLinkHub uses at least 30 ms.")
            }

            CheckBox {
                Layout.columnSpan: 2
                enabled: !panel.work.enabled
                text: qsTr("Press and hold / toggle")
                checked: !!panel.work.pressAndHold
                onToggled: panel.set("pressAndHold", checked)
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Keeps sending the action until the key is released. For mouse assignments: repeats until the key is pressed again.")
            }
            CheckBox {
                Layout.columnSpan: 2
                visible: panel.hasModifiers
                enabled: !panel.work.enabled
                text: qsTr("Retain original")
                checked: !!panel.work.retainOriginal
                onToggled: panel.set("retainOriginal", checked)
                ToolTip.visible: hovered
                ToolTip.text: qsTr("Sends the original key first, then the assigned value.")
            }

            RowLayout {
                Layout.columnSpan: 4
                Layout.alignment: Qt.AlignRight
                Button {
                    text: qsTr("Undo")
                    enabled: panel.changed
                    onClicked: panel.reset()
                }
                Button {
                    text: qsTr("Save")
                    icon.name: "document-save"
                    highlighted: panel.changed
                    enabled: panel.changed
                    onClicked: keyboard.setKeyAssignment(panel.keyId, panel.work)
                }
            }
        }
    }
}
