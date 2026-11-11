// Settings of an own widget: the fields of its widget.json (a server, a token)
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Saved right away by customwidgets/ (not with the layout). A secret is
// never shown again: the field only says whether one is stored, and an empty
// field keeps it.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: form
    property string widgetId: ""
    readonly property var widget: {
        customWidgets.widgets      // again when widgets change
        return customWidgets.widget(widgetId)
    }
    property var values: ({})
    property string error: ""
    spacing: 8

    function load() {
        values = widgetId ? customWidgets.values(widgetId) : {}
        error = ""
        for (let i = 0; i < inputs.count; i++) inputs.itemAt(i).reset()
    }
    onWidgetIdChanged: load()
    Connections {
        target: customWidgets
        function onChanged() { form.load() }
    }

    Label { text: form.widget.name || form.widgetId; font.bold: true; font.pixelSize: 18 }
    Label {
        Layout.fillWidth: true
        visible: text !== ""
        text: form.widget.description || ""
        wrapMode: Text.WordWrap
        opacity: 0.7
    }
    Label {
        Layout.fillWidth: true
        visible: form.widget.id === undefined
        text: qsTr("This own widget is not installed. Install it from the widget store, or remove it from the layout.")
        wrapMode: Text.WordWrap
        color: "#f67400"
    }
    Label {
        Layout.fillWidth: true
        visible: form.widget.id !== undefined && (form.widget.settings || []).length === 0
        text: qsTr("This widget has no settings.")
        opacity: 0.7
    }

    Repeater {
        id: inputs
        model: form.widget.settings || []
        delegate: ColumnLayout {
            id: row
            required property var modelData
            readonly property var current: form.values[modelData.name] || ({})
            function reset() { input.text = modelData.type === "secret" ? "" : (current.value || "") }
            function value() { return input.text }
            Layout.fillWidth: true
            spacing: 2
            Label { text: row.modelData.label }
            TextField {
                id: input
                Layout.fillWidth: true
                echoMode: row.modelData.type === "secret" ? TextInput.Password : TextInput.Normal
                placeholderText: row.modelData.type === "secret"
                                 ? (row.current.set ? qsTr("Saved, leave empty to keep it") : qsTr("Not set"))
                                 : row.modelData.default
                inputMethodHints: Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText
                Component.onCompleted: row.reset()
            }
            Label {
                Layout.fillWidth: true
                visible: text !== ""
                text: row.modelData.help
                wrapMode: Text.WordWrap
                opacity: 0.6
                font.pixelSize: 12
            }
        }
    }

    RowLayout {
        visible: (form.widget.settings || []).length > 0
        Label {
            Layout.fillWidth: true
            text: form.error
            color: "#da4453"
            wrapMode: Text.WordWrap
        }
        Button {
            text: qsTr("Save settings")
            icon.name: "document-save"
            onClicked: {
                const values = {}
                for (let i = 0; i < inputs.count; i++) {
                    const item = inputs.itemAt(i)
                    values[item.modelData.name] = item.value()
                }
                form.error = customWidgets.saveSettings(form.widgetId, values)
                if (form.error === "") {
                    form.load()
                    backend.notify(qsTr("Settings saved"), true)
                }
            }
        }
    }
}
