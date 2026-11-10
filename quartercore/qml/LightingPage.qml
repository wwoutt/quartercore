// Lighting: choose a device and an effect, then set its colours, speed and direction
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: page
    readonly property var effect: lighting.selected
    readonly property bool isHub: (backend.hubs || []).some(h => h.serial === lighting.serial)

    // Editor values, copied from the selected effect and sent on save
    property var work: ({})
    // Compared as text; kept apart so the comparison isn't a binding on the effect itself
    property string savedJson: ""
    readonly property bool dirty: JSON.stringify(work) !== savedJson

    function initial() {
        const e = effect
        if (!e.key)
            return {}
        // Plain copies, so editing never touches the effect from Python
        const part = p => ({ color: p.color, temperature: p.temperature })
        return {
            start: part(e.start), middle: part(e.middle), end: part(e.end),
            gradient: (e.gradient || []).map(s => ({ color: s.color, position: s.position, brightness: s.brightness })),
            speed: e.speed, direction: e.direction, alternateColors: e.alternateColors,
            minTemp: e.minTemp, maxTemp: e.maxTemp
        }
    }
    function set(key, value) {
        const copy = Object.assign({}, work)
        copy[key] = value
        work = copy
    }
    function setPart(part, key, value) {
        const copy = Object.assign({}, work[part])
        copy[key] = value
        set(part, copy)
    }
    function setStop(index, key, value) {
        const stops = work.gradient.slice()
        stops[index] = Object.assign({}, stops[index], { [key]: value })
        set("gradient", stops)
    }
    function hex(c) {
        const h = v => ("0" + Math.round(v * 255).toString(16)).slice(-2)
        return "#" + h(c.r) + h(c.g) + h(c.b)
    }

    function reset() {
        work = initial()
        savedJson = JSON.stringify(work)
    }

    onEffectChanged: reset()
    Component.onCompleted: {
        reset()
        if (lighting.devices.length === 0)
            lighting.refreshDevices()
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Device and effects
        ColumnLayout {
            Layout.preferredWidth: 260
            Layout.maximumWidth: 260
            Layout.fillHeight: true
            Layout.margins: 16
            spacing: 8

            Label { text: qsTr("Lighting"); font.pixelSize: 22 }
            ComboBox {
                id: deviceBox
                Layout.fillWidth: true
                model: lighting.devices
                textRole: "product"
                valueRole: "serial"
                currentIndex: lighting.devices.findIndex(d => d.serial === lighting.serial)
                onActivated: lighting.selectDevice(currentValue)
            }

            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: lighting.effects
                delegate: ItemDelegate {
                    width: ListView.view.width
                    highlighted: page.effect.key === modelData.key
                    onClicked: lighting.selectEffect(modelData.key)
                    contentItem: RowLayout {
                        spacing: 10
                        Rectangle {
                            width: 28; height: 16; radius: 3
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0; color: modelData.preview[0] }
                                GradientStop { position: 1; color: modelData.preview[1] }
                            }
                        }
                        Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                    }
                }
            }
        }

        ToolSeparator { Layout.fillHeight: true; orientation: Qt.Vertical; padding: 0 }

        Flickable {
            id: details
            Layout.fillWidth: true
            Layout.preferredWidth: 600
            Layout.fillHeight: true
            contentHeight: editor.implicitHeight + 32
            clip: true
            ScrollBar.vertical: ScrollBar {}

            ColumnLayout {
                id: editor
                x: 24
                y: 16
                width: details.width - 48
                spacing: 14
                visible: page.effect.key !== undefined && page.work.start !== undefined

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: page.effect.name || ""; font.pixelSize: 26; Layout.fillWidth: true }
                    Button {
                        text: qsTr("Use on all devices of this hub")
                        icon.name: "games-config-tiles"
                        visible: page.isHub
                        onClicked: lighting.applyToHub(page.effect.key)
                    }
                }

                // Two colours
                GridLayout {
                    visible: page.effect.colorMode === "two"
                    columns: 2
                    columnSpacing: 12
                    rowSpacing: 8
                    Label { text: qsTr("First colour") }
                    ColorButton {
                        value: (page.work.start || {}).color || "black"
                        onPicked: c => page.setPart("start", "color", page.hex(c))
                    }
                    Label { text: qsTr("Second colour") }
                    ColorButton {
                        value: (page.work.end || {}).color || "black"
                        onPicked: c => page.setPart("end", "color", page.hex(c))
                    }
                }

                // Colour by temperature
                GridLayout {
                    visible: page.effect.colorMode === "temperature"
                    columns: 3
                    columnSpacing: 12
                    rowSpacing: 8
                    Repeater {
                        model: [["start", qsTr("Cool")], ["middle", qsTr("Warm")], ["end", qsTr("Hot")]]
                        delegate: RowLayout {
                            required property var modelData
                            Layout.columnSpan: 3
                            spacing: 12
                            Label { text: modelData[1]; Layout.preferredWidth: 80 }
                            ColorButton {
                                value: (page.work[modelData[0]] || {}).color || "black"
                                onPicked: c => page.setPart(modelData[0], "color", page.hex(c))
                            }
                            Label { text: qsTr("at") }
                            SpinBox {
                                from: 0; to: 150
                                value: (page.work[modelData[0]] || {}).temperature || 0
                                onValueModified: page.setPart(modelData[0], "temperature", value)
                            }
                            Label { text: "°C" }
                        }
                    }
                }

                // Gradient
                ColumnLayout {
                    visible: page.effect.colorMode === "gradient"
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 36
                        radius: 6
                        color: "transparent"
                        // GradientStops can't come from a Repeater, so the bar is drawn on a Canvas
                        Canvas {
                            anchors.fill: parent
                            property var stops: page.work.gradient || []
                            onStopsChanged: requestPaint()
                            onPaint: {
                                const ctx = getContext("2d")
                                ctx.reset()
                                if (stops.length === 0) return
                                const g = ctx.createLinearGradient(0, 0, width, 0)
                                stops.slice().sort((a, b) => a.position - b.position)
                                     .forEach(s => g.addColorStop(Math.max(0, Math.min(1, s.position)), s.color))
                                ctx.fillStyle = g
                                ctx.fillRect(0, 0, width, height)
                            }
                        }
                    }

                    Repeater {
                        model: (page.work.gradient || []).length
                        delegate: RowLayout {
                            required property int index
                            readonly property var stop: page.work.gradient[index]
                            spacing: 12
                            ColorButton {
                                value: stop.color
                                onPicked: c => page.setStop(index, "color", page.hex(c))
                            }
                            Label { text: qsTr("Position") }
                            Slider {
                                Layout.fillWidth: true
                                from: 0; to: 1
                                value: stop.position
                                onMoved: page.setStop(index, "position", Math.round(value * 100) / 100)
                            }
                            Label { text: Math.round(stop.position * 100) + " %"; Layout.preferredWidth: 44 }
                            ToolButton {
                                icon.name: "list-remove"
                                enabled: page.work.gradient.length > 2
                                ToolTip.visible: hovered
                                ToolTip.text: qsTr("Remove colour")
                                onClicked: {
                                    const stops = page.work.gradient.slice()
                                    stops.splice(index, 1)
                                    page.set("gradient", stops)
                                }
                            }
                        }
                    }
                    Button {
                        text: qsTr("Add colour")
                        icon.name: "list-add"
                        onClicked: page.set("gradient", page.work.gradient.concat([{ color: "#00ffff", position: 0.5, brightness: 1 }]))
                    }
                }

                // Probe temperatures
                RowLayout {
                    visible: page.effect.probe === true
                    spacing: 12
                    Label { text: qsTr("Probe range") }
                    SpinBox {
                        from: 0; to: 100
                        value: page.work.minTemp || 0
                        onValueModified: page.set("minTemp", value)
                    }
                    Label { text: qsTr("to") }
                    SpinBox {
                        from: 0; to: 100
                        value: page.work.maxTemp || 0
                        onValueModified: page.set("maxTemp", value)
                    }
                    Label { text: "°C" }
                }

                // Speed: lower is faster in OpenLinkHub
                RowLayout {
                    Layout.fillWidth: true
                    visible: page.effect.speedFixed === false
                    spacing: 12
                    Label { text: qsTr("Speed") }
                    Label { text: qsTr("fast"); opacity: 0.7 }
                    Slider {
                        Layout.fillWidth: true
                        from: page.effect.speedMin || 1
                        to: page.effect.speedMax || 10
                        stepSize: page.effect.speedStep === 1 ? 1 : 0
                        snapMode: Slider.SnapAlways
                        value: page.work.speed || 1
                        onMoved: page.set("speed", page.effect.speedStep === 1 ? Math.round(value) : Math.round(value * 10) / 10)
                    }
                    Label { text: qsTr("slow"); opacity: 0.7 }
                }

                RowLayout {
                    visible: (page.effect.direction || 0) > 0
                    spacing: 12
                    Label { text: qsTr("Direction") }
                    ComboBox {
                        textRole: "name"
                        valueRole: "value"
                        model: lighting.directions
                        currentIndex: lighting.directions.findIndex(d => d.value === page.work.direction)
                        onActivated: page.set("direction", currentValue)
                    }
                }

                CheckBox {
                    visible: page.effect.alternating === true
                    text: qsTr("Alternate the colours")
                    checked: page.work.alternateColors === true
                    onToggled: page.set("alternateColors", checked)
                }

                RowLayout {
                    Layout.topMargin: 8
                    Button {
                        text: qsTr("Undo changes")
                        enabled: page.dirty
                        onClicked: page.reset()
                    }
                    Button {
                        text: qsTr("Save")
                        icon.name: "document-save"
                        enabled: page.dirty
                        highlighted: page.dirty
                        onClicked: lighting.save(page.work)
                    }
                }

                Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    opacity: 0.6
                    font.pixelSize: 12
                    text: qsTr("These are the settings of the effect on this device. Choose which effect a fan uses on its device page, or use the button above.")
                }
            }
        }
    }
}
