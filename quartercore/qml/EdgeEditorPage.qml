// XENEON EDGE layout editor: drag, resize, hide, add and set up the widgets
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// The preview is the real kiosk at 2560 x 720, scaled down. Drag a widget to
// move it, drag the corner to resize it; it snaps to the 24 x 12 grid and
// can't cover another widget. Nothing changes on the XENEON EDGE until "Save".
// Modified by wwoutt, 2026-11-11: own widgets and the widget store

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "edge"

Flickable {
    id: page
    contentHeight: content.implicitHeight + 32
    clip: true
    ScrollBar.vertical: ScrollBar {}

    readonly property var current: edgeEditor.selectedItem
    readonly property bool hasCurrent: current.key !== undefined

    Component.onCompleted: { edge.setPreview(true); edgeEditor.refreshChoices() }
    Component.onDestruction: edge.setPreview(false)

    WidgetStore { id: store }

    ColumnLayout {
        id: content
        x: 24
        y: 20
        width: page.width - 60
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 0
                Label { text: qsTr("XENEON EDGE layout"); font.pixelSize: 26 }
                Label {
                    text: (edge.screenName ? qsTr("Screen: %1.").arg(edge.screenName) : qsTr("No 2560 × 720 screen found."))
                          + " " + (settings.edgeKiosk ? qsTr("The kiosk is on.") : qsTr("The kiosk is off."))
                    opacity: 0.6
                }
            }
            Item { Layout.fillWidth: true }
            Switch {
                text: qsTr("Kiosk")
                checked: settings.edgeKiosk
                onToggled: settings.edgeKiosk = checked
            }
        }

        // Toolbar
        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Button {
                text: qsTr("Add widget")
                icon.name: "list-add"
                enabled: edgeEditor.available.length > 0
                onClicked: addMenu.popup()
                Menu {
                    id: addMenu
                    Repeater {
                        model: edgeEditor.available
                        delegate: MenuItem {
                            text: modelData.name
                            onTriggered: modelData.custom ? edgeEditor.addCustom(modelData.custom) : edgeEditor.add(modelData.id)
                        }
                    }
                }
            }
            Button {
                text: qsTr("Widget store")
                icon.name: "get-hot-new-stuff"
                onClicked: store.open()
            }
            Button { text: qsTr("Default widgets"); onClicked: edgeEditor.resetDefaults() }
            Button {
                text: qsTr("Take over from OpenLinkHub")
                enabled: backend.connected
                ToolTip.visible: hovered
                ToolTip.text: qsTr("The layout of the web editor and the widget settings of OpenLinkHub")
                onClicked: edgeEditor.importFromOpenLinkHub()
            }
            Item { Layout.fillWidth: true }
            Label {
                visible: edgeEditor.problem !== ""
                text: edgeEditor.problem
                color: "#f67400"
                elide: Text.ElideRight
                Layout.maximumWidth: 320
            }
            Button { text: qsTr("Undo"); enabled: edgeEditor.dirty; onClicked: edgeEditor.revert() }
            Button {
                text: qsTr("Save")
                icon.name: "document-save"
                enabled: edgeEditor.dirty && edgeEditor.problem === ""
                highlighted: enabled
                onClicked: edgeEditor.save()
            }
        }

        // Preview at scale
        Item {
            id: preview
            Layout.fillWidth: true
            Layout.preferredHeight: width * 720 / 2560
            readonly property real factor: width / 2560

            Rectangle {
                id: canvas
                width: 2560
                height: 720
                scale: preview.factor
                transformOrigin: Item.TopLeft
                color: "#07090c"
                readonly property real cellW: 2560 / edge.columns
                readonly property real cellH: 720 / edge.rows

                // Grid lines
                Repeater {
                    model: edge.columns - 1
                    Rectangle { x: (index + 1) * canvas.cellW; width: 1; height: 720; color: "#141a22" }
                }
                Repeater {
                    model: edge.rows - 1
                    Rectangle { y: (index + 1) * canvas.cellH; width: 2560; height: 1; color: "#141a22" }
                }

                Repeater {
                    model: edgeEditor.items.filter(i => !i.hidden)
                    delegate: Item {
                        id: tile
                        required property var modelData
                        readonly property bool selected: edgeEditor.selected === modelData.key
                        // Offsets while dragging, in canvas pixels
                        property real dx: 0
                        property real dy: 0
                        property real dw: 0
                        property real dh: 0
                        x: modelData.x * canvas.cellW + dx
                        y: modelData.y * canvas.cellH + dy
                        width: modelData.w * canvas.cellW + dw
                        height: modelData.h * canvas.cellH + dh
                        z: selected ? 2 : 1

                        WidgetLoader {
                            anchors.fill: parent
                            anchors.margins: 6
                            widget: tile.modelData
                            enabled: false
                        }
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 3
                            color: move.pressed ? Qt.rgba(0.24, 0.68, 0.91, 0.12) : "transparent"
                            radius: 16
                            border.width: tile.selected ? 6 : 2
                            border.color: tile.selected ? "#3daee9" : Qt.rgba(1, 1, 1, 0.15)
                        }
                        MouseArea {
                            id: move
                            anchors.fill: parent
                            // The page scrolls; without this it takes over the drag
                            preventStealing: true
                            cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                            property point start
                            onPressed: mouse => { start = mapToItem(canvas, mouse.x, mouse.y); edgeEditor.select(tile.modelData.key) }
                            onPositionChanged: mouse => {
                                const p = mapToItem(canvas, mouse.x, mouse.y)
                                tile.dx = p.x - start.x
                                tile.dy = p.y - start.y
                            }
                            onReleased: {
                                const m = tile.modelData
                                const x = Math.round((m.x * canvas.cellW + tile.dx) / canvas.cellW)
                                const y = Math.round((m.y * canvas.cellH + tile.dy) / canvas.cellH)
                                tile.dx = 0; tile.dy = 0
                                if (x !== m.x || y !== m.y) edgeEditor.place(m.key, x, y, m.w, m.h)
                            }
                        }
                        // Resize handle
                        Rectangle {
                            width: 48; height: 48
                            radius: 10
                            anchors { right: parent.right; bottom: parent.bottom; margins: 8 }
                            color: "#3daee9"
                            visible: tile.selected
                            Label { anchors.centerIn: parent; text: "⤡"; font.pixelSize: 30; color: "white" }
                            MouseArea {
                                anchors.fill: parent
                                anchors.margins: -12
                                preventStealing: true
                                cursorShape: Qt.SizeFDiagCursor
                                property point start
                                onPressed: mouse => start = mapToItem(canvas, mouse.x, mouse.y)
                                onPositionChanged: mouse => {
                                    const p = mapToItem(canvas, mouse.x, mouse.y)
                                    tile.dw = p.x - start.x
                                    tile.dh = p.y - start.y
                                }
                                onReleased: {
                                    const m = tile.modelData
                                    const w = Math.max(1, Math.round((m.w * canvas.cellW + tile.dw) / canvas.cellW))
                                    const h = Math.max(1, Math.round((m.h * canvas.cellH + tile.dh) / canvas.cellH))
                                    tile.dw = 0; tile.dh = 0
                                    if (w !== m.w || h !== m.h) edgeEditor.place(m.key, m.x, m.y, w, h)
                                }
                            }
                        }
                    }
                }
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            opacity: 0.6
            text: qsTr("Drag a widget to move it and the blue corner to resize it. Widgets can't overlap. Device sensors, batteries and profiles still come from OpenLinkHub; the other values Quartercore reads itself.")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            // Widgets in the layout
            Frame {
                Layout.preferredWidth: 300
                Layout.alignment: Qt.AlignTop
                ColumnLayout {
                    anchors.fill: parent
                    spacing: 2
                    Label { text: qsTr("Widgets"); font.bold: true }
                    Repeater {
                        model: edgeEditor.items
                        delegate: RowLayout {
                            Layout.fillWidth: true
                            CheckBox {
                                checked: !modelData.hidden
                                onToggled: edgeEditor.setHidden(modelData.key, !checked)
                                ToolTip.visible: hovered
                                ToolTip.text: qsTr("Show on the XENEON EDGE")
                            }
                            ItemDelegate {
                                Layout.fillWidth: true
                                text: qsTr(modelData.name)
                                highlighted: edgeEditor.selected === modelData.key
                                opacity: modelData.hidden ? 0.5 : 1
                                onClicked: edgeEditor.select(modelData.key)
                            }
                            ToolButton {
                                icon.name: "edit-delete"
                                ToolTip.visible: hovered
                                ToolTip.text: qsTr("Remove from the layout")
                                onClicked: edgeEditor.remove(modelData.key)
                            }
                        }
                    }
                }
            }

            // Settings of the selected widget
            Frame {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                ColumnLayout {
                    anchors.fill: parent
                    Label {
                        visible: !page.hasCurrent
                        text: qsTr("Choose a widget to change its settings.")
                        opacity: 0.7
                    }
                    WidgetSettings {
                        visible: page.hasCurrent && page.current.template !== "custom"
                        Layout.fillWidth: true
                        item: page.current
                    }
                    CustomWidgetSettings {
                        visible: page.hasCurrent && page.current.template === "custom"
                        Layout.fillWidth: true
                        widgetId: page.hasCurrent ? (page.current.custom || "") : ""
                    }
                }
            }
        }
    }
}
