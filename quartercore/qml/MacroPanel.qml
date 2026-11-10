// Macros: profiles, their steps, settings and recording
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Macros belong to OpenLinkHub, not to one keyboard: every device with key
// assignments can play them (key assignment type "Macro").

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

RowLayout {
    id: panel
    spacing: 14

    property int macroId: -1
    readonly property var macro: keyboard.macros.find(m => m.id === macroId) || null
    readonly property var keyNames: keyboard.macroValues["3"] || []

    // Recording: key presses in this window
    property bool recording: false
    property var events: []
    property double startTime: 0

    Connections {
        target: keyboard
        function onMacrosChanged() {
            if (!panel.macro && keyboard.macros.length > 0) panel.macroId = keyboard.macros[0].id
        }
        function onRecordingSaved() { panel.events = [] }
    }
    Component.onCompleted: if (keyboard.macros.length > 0) macroId = keyboard.macros[0].id

    function keyName(code) {
        const k = keyNames.find(o => o.code === code - 8)
        return k ? k.name : "?"
    }

    // --- list of macros ---
    Frame {
        Layout.preferredWidth: 190
        Layout.fillHeight: true
        Layout.minimumHeight: 220
        ColumnLayout {
            anchors.fill: parent
            spacing: 8
            Label { text: qsTr("Macros"); font.bold: true }
            ListView {
                id: list
                Layout.fillWidth: true
                Layout.preferredWidth: 160
                Layout.fillHeight: true
                clip: true
                model: keyboard.macros
                delegate: ItemDelegate {
                    width: ListView.view.width
                    text: modelData.name
                    highlighted: modelData.id === panel.macroId
                    onClicked: panel.macroId = modelData.id
                }
                Label {
                    anchors.centerIn: parent
                    visible: keyboard.macros.length === 0
                    text: qsTr("No macros yet")
                    opacity: 0.6
                }
            }
            RowLayout {
                Button {
                    text: qsTr("New…")
                    icon.name: "list-add"
                    Layout.fillWidth: true
                    onClicked: newMacro.open()
                }
                ToolButton {
                    icon.name: "edit-delete"
                    enabled: !!panel.macro
                    ToolTip.visible: hovered
                    ToolTip.text: qsTr("Delete")
                    onClicked: deleteMacro.open()
                }
            }
        }
    }

    // --- the selected macro ---
    ColumnLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        spacing: 12

        Label {
            visible: !panel.macro
            text: qsTr("Make a macro with \"New…\", add steps and assign it to a key in the key assignments tab.")
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            opacity: 0.8
        }

        // Settings: repeat and delay
        Frame {
            visible: !!panel.macro
            Layout.fillWidth: true
            RowLayout {
                anchors.fill: parent
                spacing: 10
                Label { text: panel.macro ? panel.macro.name : ""; font.bold: true; font.pixelSize: 18 }
                Item { Layout.fillWidth: true }
                CheckBox {
                    id: loop
                    text: qsTr("Loop until stopped")
                    checked: !!panel.macro && panel.macro.repeat < 0
                }
                Label { text: qsTr("Repeat"); visible: !loop.checked }
                SpinBox {
                    id: repeat
                    visible: !loop.checked
                    from: 0; to: 1000; editable: true
                    value: panel.macro ? Math.max(0, panel.macro.repeat) : 0
                }
                Label { text: qsTr("Delay (ms)") }
                SpinBox {
                    id: repeatDelay
                    from: 0; to: 60000; stepSize: 50; editable: true
                    value: panel.macro ? panel.macro.repeatDelay : 0
                }
                Button {
                    text: qsTr("Save")
                    icon.name: "document-save"
                    onClicked: keyboard.setMacroSettings(panel.macroId, loop.checked, repeat.value, repeatDelay.value)
                }
            }
        }

        // Steps
        Frame {
            visible: !!panel.macro
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                spacing: 6
                Label { text: qsTr("Steps"); font.bold: true }
                Label {
                    visible: !!panel.macro && panel.macro.steps.length === 0
                    text: qsTr("No steps yet. Add them below or record them.")
                    opacity: 0.6
                }
                Repeater {
                    model: panel.macro ? panel.macro.steps : []
                    delegate: RowLayout {
                        id: step
                        Layout.fillWidth: true
                        spacing: 8
                        readonly property bool pressable: modelData.type === 3 || modelData.type === 9 || modelData.type === 1
                        readonly property bool position: modelData.type === 20

                        Label { text: "#" + modelData.index; opacity: 0.6; Layout.preferredWidth: 30 }
                        Label { text: keyboard.macroTypeName(modelData.type); Layout.preferredWidth: 100 }
                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 70
                            elide: Text.ElideRight
                            font.bold: true
                            text: modelData.type === 5 ? qsTr("%1 ms").arg(modelData.delay)
                                : modelData.type === 6 ? "\"" + modelData.text + "\""
                                : step.position ? "" : modelData.valueName || ("#" + modelData.value)
                        }
                        CheckBox {
                            id: hold
                            visible: step.pressable
                            text: qsTr("Hold")
                            checked: modelData.pressAndHold
                        }
                        SpinBox {
                            id: stepRepeat
                            visible: step.pressable
                            from: 0; to: 100; editable: true
                            value: modelData.repeat
                            textFromValue: v => v + "×"
                            valueFromText: t => parseInt(t) || 0
                            Layout.preferredWidth: 90
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Repeat")
                        }
                        SpinBox {
                            id: stepDelay
                            visible: step.pressable
                            from: 0; to: 10000; stepSize: 10; editable: true
                            value: modelData.repeatDelay
                            textFromValue: v => qsTr("%1 ms").arg(v)
                            valueFromText: t => parseInt(t) || 0
                            Layout.preferredWidth: 110
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Delay between repeats")
                        }
                        Label { text: "X"; visible: step.position }
                        SpinBox { id: px; visible: step.position; from: 0; to: 16384; editable: true; value: modelData.x }
                        Label { text: "Y"; visible: step.position }
                        SpinBox { id: py; visible: step.position; from: 0; to: 16384; editable: true; value: modelData.y }
                        CheckBox { id: abs; visible: step.position; text: qsTr("Absolute"); checked: modelData.absolute }
                        ToolButton {
                            icon.name: "document-save"
                            visible: step.pressable || step.position
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Save step")
                            onClicked: keyboard.updateMacroStep(panel.macroId, modelData.index, {
                                pressAndHold: hold.checked, repeat: stepRepeat.value, repeatDelay: stepDelay.value,
                                x: px.value, y: py.value, absolute: abs.checked })
                        }
                        ToolButton {
                            icon.name: "edit-delete"
                            ToolTip.visible: hovered
                            ToolTip.text: qsTr("Delete step")
                            onClicked: keyboard.deleteMacroStep(panel.macroId, modelData.index)
                        }
                    }
                }
            }
        }

        // Add a step
        Frame {
            visible: !!panel.macro && !panel.recording
            Layout.fillWidth: true
            RowLayout {
                anchors.fill: parent
                spacing: 8
                Label { text: qsTr("Add") }
                ComboBox {
                    id: stepType
                    textRole: "name"
                    valueRole: "value"
                    model: keyboard.macroStepTypes
                }
                readonly property var choices: keyboard.macroValues[String(stepType.currentValue)] || []
                ComboBox {
                    id: stepValue
                    Layout.fillWidth: true
                    visible: parent.choices.length > 0
                    editable: true
                    textRole: "name"
                    valueRole: "value"
                    model: parent.choices
                    onAccepted: { const i = find(editText, Qt.MatchContains); if (i >= 0) currentIndex = i }
                }
                SpinBox {
                    id: newDelay
                    visible: stepType.currentValue === 5
                    from: 1; to: 60000; stepSize: 10; editable: true; value: 100
                }
                Label { text: qsTr("ms"); visible: stepType.currentValue === 5 }
                TextField {
                    id: newText
                    Layout.fillWidth: true
                    visible: stepType.currentValue === 6
                    placeholderText: qsTr("Text to type")
                }
                Label { text: "X"; visible: stepType.currentValue === 20 }
                SpinBox { id: newX; visible: stepType.currentValue === 20; from: 0; to: 16384; editable: true }
                Label { text: "Y"; visible: stepType.currentValue === 20 }
                SpinBox { id: newY; visible: stepType.currentValue === 20; from: 0; to: 16384; editable: true }
                CheckBox { id: newAbs; visible: stepType.currentValue === 20; text: qsTr("Absolute") }
                Item { Layout.fillWidth: true; visible: !stepValue.visible && !newText.visible }
                Button {
                    text: qsTr("Add step")
                    icon.name: "list-add"
                    onClicked: keyboard.addMacroStep(panel.macroId, {
                        type: stepType.currentValue, value: stepValue.visible ? stepValue.currentValue : 0,
                        delay: newDelay.value, text: newText.text, x: newX.value, y: newY.value, absolute: newAbs.checked })
                }
                Button {
                    text: qsTr("Record")
                    icon.name: "media-record"
                    onClicked: { panel.events = []; panel.recording = true; recorder.forceActiveFocus() }
                }
            }
        }

        // Recording
        Frame {
            visible: panel.recording
            Layout.fillWidth: true
            FocusScope {
                id: recorder
                anchors.fill: parent
                implicitHeight: recordLayout.implicitHeight
                Keys.onPressed: event => {
                    event.accepted = true
                    if (event.isAutoRepeat) return
                    const now = Date.now()
                    if (panel.events.length === 0) panel.startTime = now
                    panel.events = panel.events.concat([{ code: event.nativeScanCode, time: now - panel.startTime }])
                }
                Keys.onReleased: event => { event.accepted = true }
                ColumnLayout {
                    id: recordLayout
                    anchors.fill: parent
                    spacing: 8
                    RowLayout {
                        Rectangle { width: 12; height: 12; radius: 6; color: recorder.activeFocus ? "#da4453" : "gray" }
                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: recorder.activeFocus
                                ? qsTr("Recording: press the keys of the macro. Keys taken by the desktop (like Alt+Tab) can't be recorded.")
                                : qsTr("Click here to continue recording.")
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        font.bold: true
                        text: panel.events.length === 0 ? "…" : panel.events.map(e => panel.keyName(e.code)).join("  ")
                    }
                    RowLayout {
                        CheckBox { id: withDelays; text: qsTr("Keep the pauses between keys"); checked: true }
                        Item { Layout.fillWidth: true }
                        Button {
                            text: qsTr("Cancel")
                            onClicked: { panel.recording = false; panel.events = [] }
                        }
                        Button {
                            text: qsTr("Stop and add %1 keys").arg(panel.events.length)
                            icon.name: "media-playback-stop"
                            highlighted: true
                            enabled: panel.events.length > 0
                            onClicked: {
                                panel.recording = false
                                keyboard.saveRecording(panel.macroId, panel.events, withDelays.checked)
                            }
                        }
                    }
                }
                MouseArea {
                    anchors.fill: parent
                    z: -1
                    onClicked: recorder.forceActiveFocus()
                }
            }
        }

        // OpenLinkHub numbers a new step with the number of steps, so after a gap it replaces the last step
        Label {
            visible: !!panel.macro && panel.macro.steps.some((s, i) => s.index !== i)
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#f67400"
            text: qsTr("The step numbers of this macro have a gap: OpenLinkHub lets a new step replace the last one. Delete the steps after the gap and add them again first.")
        }
    }

    Dialog {
        id: newMacro
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: qsTr("New macro")
        standardButtons: Dialog.Ok | Dialog.Cancel
        onOpened: { macroName.text = ""; macroName.forceActiveFocus() }
        onAccepted: keyboard.newMacro(macroName.text)
        TextField {
            id: macroName
            width: 260
            placeholderText: qsTr("At least 3 letters or digits")
            validator: RegularExpressionValidator { regularExpression: /[a-zA-Z0-9]*/ }
            onAccepted: newMacro.accept()
        }
    }

    Dialog {
        id: deleteMacro
        parent: Overlay.overlay
        anchors.centerIn: parent
        modal: true
        title: qsTr("Delete macro %1?").arg(panel.macro ? panel.macro.name : "")
        standardButtons: Dialog.Yes | Dialog.No
        Label { text: qsTr("Keys assigned to this macro need a new assignment.") }
        onAccepted: {
            keyboard.deleteMacro(panel.macroId)
            panel.macroId = -1
        }
    }
}
