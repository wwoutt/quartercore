// The tiles of a Home Assistant widget in the layout editor
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Every tile is one entity: a tap switches or presses it. A tile can show the state of
// another entity instead (a garage button with the door sensor as status), and has its
// own rules: "when the state is on: orange, text Open". The first rule that fits wins;
// "> 25" and "< 10" compare numbers. Stored in the "entities" setting as JSON
// (homeassistant.tile_specs), or as a plain list when no tile has a status or rules.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: editor
    property string text: ""            // the "entities" setting
    signal edited(string text)
    spacing: 8

    property var entityList: []
    Component.onCompleted: { homeAssistant.refresh(); entityList = homeAssistant.entities() }
    Connections {
        target: homeAssistant
        function onStatesChanged() { editor.entityList = homeAssistant.entities() }
    }

    // --- the stored tiles ---
    readonly property var tiles: parse(text)

    function parse(t) {
        t = String(t || "").trim()
        let raw = []
        if (t.startsWith("[")) {
            try { raw = JSON.parse(t) } catch (e) { raw = [] }
        } else {
            raw = t.split(/[,\n]/).map(p => {
                const parts = p.split(">").map(q => q.trim())
                return { entity: parts[0], status: parts[1] || "" }
            })
        }
        return raw.filter(x => x && String(x.entity || "").indexOf(".") > 0)
                  .map(x => ({ entity: String(x.entity).trim(), status: String(x.status || "").trim(),
                               rules: (x.rules || []).map(r => ({ state: String(r.state || ""),
                                                                 color: String(r.color || ""),
                                                                 text: String(r.text || "") })) }))
    }
    function save(list) {
        const simple = list.every(x => !x.status && x.rules.length === 0)
        edited(simple ? list.map(x => x.entity).join(", ") : JSON.stringify(list))
    }
    function copy() { return JSON.parse(JSON.stringify(tiles)) }
    function change(index, fn) { const list = copy(); fn(list[index]); save(list) }
    function addTile(entity) {
        const list = copy()
        if (!list.some(x => x.entity === entity)) list.push({ entity: entity, status: "", rules: [] })
        save(list)
    }
    function move(index, by) {
        const list = copy()
        const to = index + by
        if (to < 0 || to >= list.length) return
        const t = list[index]; list[index] = list[to]; list[to] = t
        save(list)
    }
    function hex(c) {
        const h = v => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + h(c.r) + h(c.g) + h(c.b)
    }

    // Search the known entities; picked(value) for a click or Enter
    component EntitySearch: ColumnLayout {
        id: search
        property string placeholder: ""
        signal picked(string value)
        spacing: 2
        TextField {
            id: query
            Layout.fillWidth: true
            placeholderText: search.placeholder
            onAccepted: if (results.count > 0) search.choose(results.model[0].value)
        }
        Label {
            visible: query.text.trim() !== "" && results.count === 0
            text: qsTr("No entities found")
            opacity: 0.7
        }
        ListView {
            id: results
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, 240)
            visible: count > 0
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar {}
            // Every word must be in the name or the entity id; at most 200 results
            model: {
                const words = query.text.toLowerCase().split(/\s+/).filter(w => w !== "")
                if (!words.length) return []
                return editor.entityList.filter(e => {
                    const name = e.name.toLowerCase()
                    return words.every(w => name.indexOf(w) >= 0)
                }).slice(0, 200)
            }
            delegate: ItemDelegate {
                required property var modelData
                width: ListView.view.width
                text: modelData.name
                icon.name: "list-add"
                onClicked: search.choose(modelData.value)
            }
        }
        function choose(value) { query.text = ""; picked(value) }
    }

    Label {
        text: qsTr("Tiles")
        font.bold: true
    }
    Label {
        visible: editor.entityList.length === 0
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        opacity: 0.7
        text: qsTr("Connect Home Assistant in the settings to choose entities")
    }
    EntitySearch {
        visible: editor.entityList.length > 0
        Layout.fillWidth: true
        placeholder: qsTr("Search an entity to add a tile…")
        onPicked: value => editor.addTile(value)
    }

    Repeater {
        model: editor.tiles
        delegate: Frame {
            id: tileFrame
            required property var modelData
            required property int index
            readonly property string source: modelData.status || modelData.entity   // whose state the rules read
            property bool choosingStatus: false
            Layout.fillWidth: true

            ColumnLayout {
                anchors.fill: parent
                spacing: 6

                // The entity a tap switches
                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        text: homeAssistant.name(tileFrame.modelData.entity)
                        font.bold: true
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                        ToolTip.visible: tileHover.hovered
                        ToolTip.text: tileFrame.modelData.entity
                        HoverHandler { id: tileHover }
                    }
                    Label { text: tileFrame.modelData.entity; opacity: 0.6; elide: Text.ElideMiddle; Layout.maximumWidth: 320 }
                    ToolButton {
                        icon.name: "go-up"
                        enabled: tileFrame.index > 0
                        ToolTip.visible: hovered; ToolTip.text: qsTr("Move up")
                        onClicked: editor.move(tileFrame.index, -1)
                    }
                    ToolButton {
                        icon.name: "go-down"
                        enabled: tileFrame.index < editor.tiles.length - 1
                        ToolTip.visible: hovered; ToolTip.text: qsTr("Move down")
                        onClicked: editor.move(tileFrame.index, 1)
                    }
                    ToolButton {
                        icon.name: "edit-delete"
                        ToolTip.visible: hovered; ToolTip.text: qsTr("Remove this tile")
                        onClicked: { const list = editor.copy(); list.splice(tileFrame.index, 1); editor.save(list) }
                    }
                }

                // The entity whose state the tile shows
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: qsTr("Status from"); Layout.preferredWidth: 150 }
                    Label {
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                        text: tileFrame.modelData.status
                              ? homeAssistant.name(tileFrame.modelData.status) + " (" + tileFrame.modelData.status + ")"
                              : qsTr("this entity itself")
                        opacity: tileFrame.modelData.status ? 1 : 0.7
                    }
                    Button {
                        text: tileFrame.modelData.status ? qsTr("Other entity…") : qsTr("Another entity…")
                        icon.name: "search"
                        checkable: true
                        checked: tileFrame.choosingStatus
                        onClicked: tileFrame.choosingStatus = checked
                    }
                    ToolButton {
                        visible: !!tileFrame.modelData.status
                        icon.name: "edit-clear"
                        ToolTip.visible: hovered; ToolTip.text: qsTr("Show the state of this entity itself")
                        onClicked: editor.change(tileFrame.index, t => t.status = "")
                    }
                }
                EntitySearch {
                    visible: tileFrame.choosingStatus
                    Layout.fillWidth: true
                    placeholder: qsTr("Search the entity whose state this tile shows, e.g. a door sensor…")
                    onPicked: value => { tileFrame.choosingStatus = false; editor.change(tileFrame.index, t => t.status = value) }
                }

                // Rules: a state gives the tile a colour and a text
                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.7
                    font.pixelSize: 12
                    text: qsTr("Rules: when the state is…, the tile gets this colour and text. The first rule that fits counts; \"> 25\" or \"< 10\" compare numbers.")
                }
                Repeater {
                    model: tileFrame.modelData.rules
                    delegate: RowLayout {
                        id: ruleRow
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        Label { text: qsTr("When the state is"); Layout.preferredWidth: 150 }
                        ComboBox {
                            id: stateBox
                            Layout.preferredWidth: 200
                            editable: true
                            model: homeAssistant.stateOptions(tileFrame.source)
                            // After the model, or the first option would replace the stored state
                            Component.onCompleted: Qt.callLater(() => {
                                const i = find(ruleRow.modelData.state)
                                if (i >= 0) currentIndex = i
                                editText = ruleRow.modelData.state
                            })
                            function commit(value) {
                                if (value !== ruleRow.modelData.state)
                                    editor.change(tileFrame.index, t => t.rules[ruleRow.index].state = value)
                            }
                            onActivated: commit(currentText)
                            onAccepted: commit(editText)
                            onActiveFocusChanged: if (!activeFocus) commit(editText)
                        }
                        ColorButton {
                            value: ruleRow.modelData.color || "#38bdf8"
                            dialogTitle: qsTr("Colour of the tile")
                            onPicked: c => editor.change(tileFrame.index, t => t.rules[ruleRow.index].color = editor.hex(c))
                        }
                        TextField {
                            Layout.fillWidth: true
                            placeholderText: qsTr("Text on the tile (empty: the state)")
                            text: ruleRow.modelData.text
                            onEditingFinished: if (text !== ruleRow.modelData.text)
                                editor.change(tileFrame.index, t => t.rules[ruleRow.index].text = text)
                        }
                        ToolButton {
                            icon.name: "edit-delete"
                            ToolTip.visible: hovered; ToolTip.text: qsTr("Remove this rule")
                            onClicked: editor.change(tileFrame.index, t => t.rules.splice(ruleRow.index, 1))
                        }
                    }
                }
                Button {
                    text: qsTr("Add a rule")
                    icon.name: "list-add"
                    onClicked: editor.change(tileFrame.index, t => {
                        const used = t.rules.map(r => r.state)
                        const next = homeAssistant.stateOptions(tileFrame.source).find(o => used.indexOf(o) < 0) || ""
                        t.rules.push({ state: next || "on", color: "#38bdf8", text: "" })
                    })
                }
            }
        }
    }
}
