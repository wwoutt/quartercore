// Keyboard performance (disable Win key, Alt+Tab, ...) and control dial colours
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: panel
    property bool hasDial: false
    spacing: 14

    // Edited values; empty means "as OpenLinkHub has them"
    property var perf: ({})
    property var dial: ({})
    Connections {
        target: keyboard
        function onDataChanged() { panel.perf = ({}); panel.dial = ({}) }
    }
    function value(p) { return panel.perf[p.internal] !== undefined ? panel.perf[p.internal] : p.value }
    function colour(c) { return panel.dial[String(c.id)] || c.color }
    function hex(c) {
        const h = v => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + h(c.r) + h(c.g) + h(c.b)
    }

    Frame {
        Layout.fillWidth: true
        visible: keyboard.performance.length > 0
        ColumnLayout {
            anchors.fill: parent
            spacing: 6
            RowLayout {
                Label { text: qsTr("Performance"); font.bold: true; Layout.fillWidth: true }
                Button {
                    text: qsTr("Save")
                    icon.name: "document-save"
                    enabled: Object.keys(panel.perf).length > 0
                    highlighted: enabled
                    onClicked: keyboard.setPerformance(panel.perf)
                }
            }
            Label {
                text: qsTr("Turn off keys and shortcuts that get in the way while gaming.")
                opacity: 0.7
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Flow {
                Layout.fillWidth: true
                spacing: 16
                Repeater {
                    model: keyboard.performance
                    delegate: Switch {
                        text: modelData.name
                        checked: panel.value(modelData)
                        onToggled: {
                            const copy = Object.assign({}, panel.perf)
                            copy[modelData.internal] = checked
                            panel.perf = copy
                        }
                    }
                }
            }
        }
    }

    Frame {
        Layout.fillWidth: true
        visible: panel.hasDial && keyboard.dialColors.length > 0
        ColumnLayout {
            anchors.fill: parent
            spacing: 6
            RowLayout {
                Label { text: qsTr("Control dial colours"); font.bold: true; Layout.fillWidth: true }
                Button {
                    text: qsTr("Save")
                    icon.name: "document-save"
                    enabled: Object.keys(panel.dial).length > 0
                    highlighted: enabled
                    onClicked: keyboard.setDialColors(panel.dial)
                }
            }
            Label {
                text: qsTr("The dial lights up in this colour while it controls that function.")
                opacity: 0.7
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }
            Flow {
                Layout.fillWidth: true
                spacing: 12
                Repeater {
                    model: keyboard.dialColors
                    delegate: RowLayout {
                        spacing: 8
                        ColorButton {
                            value: panel.colour(modelData)
                            dialogTitle: modelData.name
                            onPicked: c => {
                                const copy = Object.assign({}, panel.dial)
                                copy[String(modelData.id)] = panel.hex(c)
                                panel.dial = copy
                            }
                        }
                        Label { text: modelData.name; Layout.preferredWidth: 140; elide: Text.ElideRight }
                    }
                }
            }
        }
    }
}
