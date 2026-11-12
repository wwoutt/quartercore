// Settings form of one XENEON EDGE widget, built from the fields in edgelayout.py
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
// Modified by wwoutt, 2026-11-11: Home Assistant tiles in their own editor (HaTilesEditor.qml)

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: form
    property var item: ({})
    readonly property var values: item.settings || ({})
    readonly property var fieldList: item.template ? edgeEditor.fields(item.template) : []
    spacing: 8

    function set(name, value) { edgeEditor.setSetting(item.key, name, value) }
    function shown(field) {
        if (!field.showIf) return true
        const parts = field.showIf.split("=")
        return String(values[parts[0]]) === parts[1]
    }
    function hex(c) {
        const h = v => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + h(c.r) + h(c.g) + h(c.b)
    }

    Label { text: qsTr(form.item.name || ""); font.bold: true; font.pixelSize: 18 }

    // Weather: look a city up (Open-Meteo), only when the button is pressed
    RowLayout {
        visible: form.item.template === "xeneon-weather"
        Layout.fillWidth: true
        TextField {
            id: citySearch
            Layout.fillWidth: true
            placeholderText: qsTr("Search a city, e.g. Utrecht")
            onAccepted: edgeEditor.searchCity(text)
        }
        Button { text: qsTr("Search"); icon.name: "search"; onClicked: edgeEditor.searchCity(citySearch.text) }
    }
    Flow {
        id: cities
        visible: form.item.template === "xeneon-weather" && results.length > 0
        Layout.fillWidth: true
        spacing: 6
        property var results: []
        Connections {
            target: edgeEditor
            function onCitiesFound(list) { cities.results = list }
            function onSelectionChanged() { if (edgeEditor.selected !== form.item.key) cities.results = [] }
        }
        Repeater {
            model: cities.results
            delegate: Button {
                text: modelData.name + (modelData.admin ? ", " + modelData.admin : "") + ", " + modelData.country
                onClicked: { edgeEditor.setCity(form.item.key, modelData); cities.results = [] }
            }
        }
    }

    GridLayout {
        id: grid
        Layout.fillWidth: true
        // Two columns only when there is room for them
        columns: width > 760 ? 2 : 1
        uniformCellWidths: true
        columnSpacing: 14
        rowSpacing: 8

        Repeater {
            model: form.fieldList
            delegate: RowLayout {
                id: row
                required property var modelData
                readonly property var field: modelData
                readonly property var value: form.values[field.name]
                visible: form.shown(field) && field.kind !== "haEntities"     // see HaTilesEditor below
                Layout.fillWidth: true
                Layout.preferredWidth: (grid.width - grid.columnSpacing * (grid.columns - 1)) / grid.columns
                spacing: 10

                Label { text: row.field.label; Layout.preferredWidth: 170; elide: Text.ElideRight }

                Loader {
                    Layout.fillWidth: true
                    sourceComponent: row.field.kind === "color" ? colorField
                                   : row.field.kind === "int" ? intField
                                   : row.field.kind === "float" || row.field.kind === "text" ? textField
                                   : row.field.kind === "bool" ? boolField
                                   : choiceField

                    Component {
                        id: colorField
                        RowLayout {
                            ColorButton {
                                value: row.value || "#000000"
                                dialogTitle: row.field.label
                                onPicked: c => form.set(row.field.name, form.hex(c))
                            }
                            Item { Layout.fillWidth: true }
                        }
                    }
                    Component {
                        id: intField
                        SpinBox {
                            from: row.field.min
                            to: row.field.max
                            editable: true
                            value: row.value || 0
                            onValueModified: form.set(row.field.name, value)
                        }
                    }
                    Component {
                        id: textField
                        TextField {
                            width: parent ? parent.width : implicitWidth
                            text: row.value === undefined || row.value === null ? "" : String(row.value)
                            validator: row.field.kind === "float" ? numberCheck : null
                            onEditingFinished: form.set(row.field.name, text)
                            DoubleValidator { id: numberCheck; bottom: row.field.min ?? -1e9; top: row.field.max ?? 1e9; locale: "C" }
                        }
                    }
                    Component {
                        id: boolField
                        CheckBox { checked: !!row.value; onToggled: form.set(row.field.name, checked) }
                    }
                    Component {
                        id: choiceField
                        ComboBox {
                            width: parent ? parent.width : implicitWidth
                            textRole: "name"
                            valueRole: "value"
                            model: {
                                edgeEditor.choicesVersion   // reload when OpenLinkHub's devices arrive
                                return row.field.choices
                                    || edgeEditor.choices(row.field.kind, String(form.values.deviceId || ""))
                            }
                            currentIndex: model.findIndex(o => o.value === row.value)
                            onActivated: form.set(row.field.name, currentValue)
                        }
                    }
                }
            }
        }
    }

    // Home Assistant: the tiles, each with an optional status entity and colour rules
    HaTilesEditor {
        Layout.fillWidth: true
        visible: form.fieldList.some(f => f.kind === "haEntities")
        text: form.values.entities || ""
        onEdited: text => form.set("entities", text)
    }
}
