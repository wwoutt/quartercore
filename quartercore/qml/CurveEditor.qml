// Speed curve: temperature (x) to speed (y), with draggable points
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Drag a point to move it, double-click to add one, right-click a point to
// remove it. Points past maxTemp (OpenLinkHub uses 200 °C as "and above") are
// drawn at the right edge and keep their temperature until moved.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: editor
    property string title
    property var points: []
    property int maxTemp: 100
    property bool editable: false
    property color lineColor: "#38bdf8"
    readonly property bool changed: JSON.stringify(work) !== JSON.stringify(sorted(points))

    signal save(var points)

    property var work: []
    onPointsChanged: reset()
    Component.onCompleted: reset()

    function sorted(list) {
        return (list || []).map(p => ({ x: p.x, y: p.y })).sort((a, b) => a.x - b.x)
    }
    function reset() {
        work = sorted(points)
        canvas.requestPaint()
    }

    SystemPalette { id: pal }

    RowLayout {
        Layout.fillWidth: true
        Label { text: editor.title; font.pixelSize: 16; font.bold: true }
        Item { Layout.fillWidth: true }
        Button {
            text: qsTr("Undo changes")
            visible: editor.editable
            enabled: editor.changed
            onClicked: editor.reset()
        }
        Button {
            text: qsTr("Save")
            icon.name: "document-save"
            visible: editor.editable
            enabled: editor.changed
            highlighted: editor.changed
            onClicked: editor.save(editor.work)
        }
    }

    Canvas {
        id: canvas
        Layout.fillWidth: true
        Layout.preferredHeight: 260
        readonly property real margin: 44
        readonly property real plotW: width - 2 * margin
        readonly property real plotH: height - 2 * margin
        property int dragIndex: -1

        function toX(t) { return margin + Math.min(t, editor.maxTemp) / editor.maxTemp * plotW }
        function toY(s) { return height - margin - s / 100 * plotH }
        function toTemp(x) { return Math.max(0, Math.min(editor.maxTemp, (x - margin) / plotW * editor.maxTemp)) }
        function toSpeed(y) { return Math.max(0, Math.min(100, (height - margin - y) / plotH * 100)) }
        function hit(mx, my) {
            for (let i = 0; i < editor.work.length; i++) {
                const p = editor.work[i]
                if (Math.hypot(toX(p.x) - mx, toY(p.y) - my) < 12)
                    return i
            }
            return -1
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            ctx.font = "11px sans-serif"
            // Grid and labels
            ctx.strokeStyle = Qt.rgba(pal.text.r, pal.text.g, pal.text.b, 0.12)
            ctx.fillStyle = Qt.rgba(pal.text.r, pal.text.g, pal.text.b, 0.6)
            ctx.lineWidth = 1
            for (let s = 0; s <= 100; s += 20) {
                const y = toY(s)
                ctx.beginPath(); ctx.moveTo(margin, y); ctx.lineTo(width - margin, y); ctx.stroke()
                ctx.textAlign = "right"; ctx.fillText(s + " %", margin - 6, y + 4)
            }
            const step = editor.maxTemp <= 60 ? 10 : 20
            for (let t = 0; t <= editor.maxTemp; t += step) {
                const x = toX(t)
                ctx.beginPath(); ctx.moveTo(x, margin); ctx.lineTo(x, height - margin); ctx.stroke()
                ctx.textAlign = "center"; ctx.fillText(t + " °C", x, height - margin + 16)
            }
            const pts = editor.work
            if (pts.length === 0)
                return
            // Curve, flat before the first and after the last point
            ctx.strokeStyle = editor.lineColor
            ctx.lineWidth = 2.5
            ctx.beginPath()
            ctx.moveTo(margin, toY(pts[0].y))
            pts.forEach(p => ctx.lineTo(toX(p.x), toY(p.y)))
            ctx.lineTo(width - margin, toY(pts[pts.length - 1].y))
            ctx.stroke()
            // Points
            pts.forEach((p, i) => {
                ctx.beginPath()
                ctx.arc(toX(p.x), toY(p.y), i === dragIndex ? 8 : 6, 0, 2 * Math.PI)
                ctx.fillStyle = editor.editable ? editor.lineColor : Qt.rgba(pal.text.r, pal.text.g, pal.text.b, 0.5)
                ctx.fill()
            })
            if (dragIndex >= 0) {
                const p = pts[dragIndex]
                ctx.fillStyle = pal.text
                ctx.textAlign = "left"
                ctx.fillText(p.x + " °C → " + p.y + " %", toX(p.x) + 10, toY(p.y) - 10)
            }
        }

        MouseArea {
            anchors.fill: parent
            enabled: editor.editable
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            hoverEnabled: true
            cursorShape: canvas.hit(mouseX, mouseY) >= 0 ? Qt.PointingHandCursor : Qt.CrossCursor

            onPressed: mouse => {
                const i = canvas.hit(mouse.x, mouse.y)
                if (mouse.button === Qt.RightButton) {
                    if (i >= 0 && editor.work.length > 2) {
                        const copy = editor.work.slice()
                        copy.splice(i, 1)
                        editor.work = copy
                        canvas.requestPaint()
                    }
                    return
                }
                canvas.dragIndex = i
                canvas.requestPaint()
            }
            onPositionChanged: mouse => {
                if (canvas.dragIndex < 0 || !pressed)
                    return
                const copy = editor.work.slice()
                copy[canvas.dragIndex] = { x: Math.round(canvas.toTemp(mouse.x)), y: Math.round(canvas.toSpeed(mouse.y)) }
                editor.work = copy
                canvas.requestPaint()
            }
            onReleased: {
                if (canvas.dragIndex >= 0) {
                    editor.work = editor.sorted(editor.work)
                    canvas.dragIndex = -1
                    canvas.requestPaint()
                }
            }
            onDoubleClicked: mouse => {
                if (canvas.hit(mouse.x, mouse.y) >= 0)
                    return
                editor.work = editor.sorted(editor.work.concat([
                    { x: Math.round(canvas.toTemp(mouse.x)), y: Math.round(canvas.toSpeed(mouse.y)) }]))
                canvas.requestPaint()
            }
        }
    }

    Label {
        visible: editor.editable
        text: qsTr("Drag a point to change it, double-click to add a point, right-click a point to remove it.")
        opacity: 0.6
        font.pixelSize: 12
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
    }
}
