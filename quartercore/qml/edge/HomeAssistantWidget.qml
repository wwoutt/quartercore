// Home Assistant: entity tiles (state) or big buttons; a tap toggles, presses or starts
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// The entities and their states come from homeassistant.py through edge.data.
// Sensors and other entities that can't be switched only show their state.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""
    readonly property bool buttons: widget.template === "xeneon-ha-buttons"
    readonly property var tiles: info.tiles || []
    // Columns so the tiles fill the card: more in a wide card
    readonly property int columns: Math.max(1, Math.min(tiles.length, Math.round(width / (buttons ? 200 : 260))))

    Label {
        visible: !info.available || (info.message && card.tiles.length === 0)
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: info.message || ""
        color: card.subTextColor
        font.pixelSize: card.unit * 1.1
    }
    GridLayout {
        id: grid
        visible: !!info.available
        anchors.fill: parent
        columns: card.columns
        rowSpacing: 8
        columnSpacing: 8
        Repeater {
            model: card.tiles
            delegate: Rectangle {
                required property var modelData
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                Layout.preferredHeight: 1
                radius: 10
                color: modelData.on ? Qt.rgba(card.accent.r, card.accent.g, card.accent.b, card.buttons ? 0.55 : 0.25)
                                    : "#1a212b"
                border.color: modelData.on ? card.accent : "#26303c"
                opacity: modelData.available ? (tap.pressed ? 0.7 : 1) : 0.45

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 2
                    Label {
                        text: modelData.name
                        color: card.textColor
                        font.pixelSize: card.buttons ? Math.min(card.unit * 1.5, parent.height * 0.35) : card.unit * 1.05
                        font.bold: card.buttons
                        wrapMode: Text.WordWrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                        horizontalAlignment: card.buttons ? Text.AlignHCenter : Text.AlignLeft
                    }
                    Item { Layout.fillHeight: true; visible: card.buttons }
                    Label {
                        visible: !card.buttons || !modelData.actionable
                        text: (modelData.translate ? qsTr(modelData.state) : modelData.state)
                              + (modelData.unit ? " " + modelData.unit : "")
                        color: modelData.on ? card.textColor : card.subTextColor
                        font.pixelSize: card.buttons ? card.unit * 1.1 : card.unit * 1.8
                        font.bold: !card.buttons
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                        horizontalAlignment: card.buttons ? Text.AlignHCenter : Text.AlignLeft
                    }
                    Item { Layout.fillHeight: true; visible: !card.buttons }
                }
                MouseArea {
                    id: tap
                    anchors.fill: parent
                    enabled: modelData.actionable && modelData.available && card.enabled
                    onClicked: edge.activateEntity(modelData.entity)
                }
            }
        }
    }
}
