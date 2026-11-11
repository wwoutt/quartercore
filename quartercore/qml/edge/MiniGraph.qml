// A small area graph of values 0-1, newest on the right (network, power)
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// A Canvas, so the graph stays inside its own box.

import QtQuick

Canvas {
    id: graph
    property var values: []
    property color color: "#38bdf8"
    property int slots: 60
    onValuesChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        const ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        const n = Math.max(2, Math.max(slots, values.length))
        const start = n - values.length
        if (values.length < 2 || width <= 0 || height <= 0)
            return
        const x = i => (start + i) / (n - 1) * width
        const y = v => height - Math.max(0, Math.min(1, v)) * (height - 2) - 1
        ctx.beginPath()
        ctx.moveTo(x(0), height)
        for (let i = 0; i < values.length; i++)
            ctx.lineTo(x(i), y(values[i]))
        ctx.lineTo(x(values.length - 1), height)
        ctx.closePath()
        ctx.fillStyle = Qt.rgba(color.r, color.g, color.b, 0.18)
        ctx.fill()
        ctx.beginPath()
        for (let i = 0; i < values.length; i++) {
            if (i === 0) ctx.moveTo(x(i), y(values[i]))
            else ctx.lineTo(x(i), y(values[i]))
        }
        ctx.strokeStyle = color
        ctx.lineWidth = 2.5
        ctx.stroke()
    }
}
