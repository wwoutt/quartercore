// Temperature profiles: list on the left, fan and pump curves on the right
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    readonly property var current: profiles.selected

    // Selects Normal once the list has loaded, when nothing is selected yet
    Component.onCompleted: profiles.refresh()

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Profile list
        ColumnLayout {
            Layout.preferredWidth: 260
            Layout.maximumWidth: 260
            Layout.fillHeight: true
            Layout.margins: 16
            spacing: 8

            Label { text: qsTr("Temperature profiles"); font.pixelSize: 22 }
            Label {
                text: qsTr("A profile sets how fast fans and pumps run at each temperature.")
                wrapMode: Text.WordWrap
                opacity: 0.7
                Layout.fillWidth: true
            }

            ListView {
                id: list
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: profiles.list
                delegate: ItemDelegate {
                    width: ListView.view.width
                    highlighted: page.current.name === modelData.name
                    onClicked: profiles.select(modelData.name)
                    contentItem: ColumnLayout {
                        spacing: 0
                        Label { text: modelData.name; font.bold: true }
                        Label {
                            text: modelData.sensorName
                                  + (modelData.builtin ? " · " + qsTr("built-in") : "")
                                  + (modelData.linear ? " · " + qsTr("linear") : "")
                                  + (modelData.static ? " · " + qsTr("static") : "")
                                  + (modelData.zeroRpm ? " · " + qsTr("zero RPM") : "")
                            opacity: 0.6
                            font.pixelSize: 12
                        }
                    }
                }
            }

            Button {
                Layout.fillWidth: true
                text: qsTr("New profile…")
                icon.name: "list-add"
                onClicked: newDialog.open()
            }
        }

        ToolSeparator { Layout.fillHeight: true; orientation: Qt.Vertical; padding: 0 }

        // Curves of the selected profile
        Flickable {
            id: details
            Layout.fillWidth: true
            Layout.preferredWidth: 600
            Layout.fillHeight: true
            contentHeight: detailColumn.implicitHeight + 32
            clip: true
            ScrollBar.vertical: ScrollBar {}

            ColumnLayout {
                id: detailColumn
                x: 24
                y: 16
                width: details.width - 48
                spacing: 16
                visible: page.current.name !== undefined

                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        spacing: 0
                        Label { text: page.current.name || ""; font.pixelSize: 26 }
                        Label {
                            text: qsTr("Sensor: %1").arg(page.current.sensorName || "–")
                                  + (page.current.zeroRpm ? " · " + qsTr("fans may stop when cool (zero RPM)") : "")
                            opacity: 0.7
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: qsTr("Delete")
                        icon.name: "edit-delete"
                        visible: page.current.builtin === false
                        onClicked: deleteDialog.open()
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    visible: page.current.editable === false
                    text: page.current.builtin ? qsTr("Built-in profiles can't be changed. Create your own profile to set your own curve.")
                        : page.current.linear ? qsTr("A linear profile follows the temperature on its own and has no curve to edit.")
                        : qsTr("A static profile runs at one fixed speed and has no curve to edit.")
                    opacity: 0.8
                }

                CurveEditor {
                    Layout.fillWidth: true
                    title: qsTr("Fans")
                    points: page.current.fans || []
                    maxTemp: page.current.maxTemp || 100
                    editable: page.current.editable === true
                    onSave: pts => profiles.saveCurve("fans", pts)
                }

                CurveEditor {
                    Layout.fillWidth: true
                    title: qsTr("Pump")
                    points: page.current.pump || []
                    maxTemp: page.current.maxTemp || 100
                    editable: page.current.editable === true
                    lineColor: "#a78bfa"
                    onSave: pts => profiles.saveCurve("pump", pts)
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.6
                    font.pixelSize: 12
                    text: qsTr("Assign a profile to a fan or pump on its device page. These curves are used when \"graphProfiles\" is on in the OpenLinkHub configuration.")
                }
            }
        }
    }

    Dialog {
        id: deleteDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("Delete profile %1?").arg(page.current.name || "")
        standardButtons: Dialog.Yes | Dialog.No
        Label {
            text: qsTr("Fans and pumps that use it go back to the Normal profile.")
            wrapMode: Text.WordWrap
        }
        onAccepted: profiles.remove(page.current.name)
    }

    Dialog {
        id: newDialog
        anchors.centerIn: parent
        width: Math.min(page.width - 48, 460)
        modal: true
        title: qsTr("New temperature profile")
        standardButtons: Dialog.Ok | Dialog.Cancel
        onOpened: { name.text = ""; name.forceActiveFocus() }
        onAccepted: profiles.create(name.text, sensor.currentValue, zeroRpm.checked,
                                    kind.currentIndex === 1, kind.currentIndex === 2,
                                    storage.currentValue || "")

        GridLayout {
            anchors.fill: parent
            columns: 2
            columnSpacing: 12
            rowSpacing: 8

            Label { text: qsTr("Name") }
            TextField {
                id: name
                Layout.fillWidth: true
                placeholderText: qsTr("Letters and digits, e.g. Gaming")
                validator: RegularExpressionValidator { regularExpression: /[a-zA-Z0-9]*/ }
            }

            Label { text: qsTr("Sensor") }
            ComboBox {
                id: sensor
                Layout.fillWidth: true
                textRole: "name"
                valueRole: "id"
                model: profiles.sensors
            }

            Label { text: qsTr("Drive"); visible: sensor.currentValue === 3 }
            ComboBox {
                id: storage
                Layout.fillWidth: true
                visible: sensor.currentValue === 3
                textRole: "Model"
                valueRole: "Key"
                model: backend.system.storage || []
            }

            Label { text: qsTr("Type") }
            ComboBox {
                id: kind
                Layout.fillWidth: true
                model: [qsTr("Curve (editable)"), qsTr("Static (one fixed speed)"), qsTr("Linear (follows the temperature)")]
            }

            Item { width: 1 }
            CheckBox {
                id: zeroRpm
                text: qsTr("Let fans stop when cool (zero RPM)")
            }
        }
    }
}
