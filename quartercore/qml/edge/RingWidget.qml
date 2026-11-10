// CPU/GPU temperature and load, device temperature and RPM: an 85 % ring gauge
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Shapes

EdgeCard {
    id: card
    title: settings.headerText || ""
    readonly property var value: info.value
    readonly property bool hasValue: value !== undefined && value !== null
    readonly property real maximum: Math.max(1, settings.max || 100)
    readonly property real fraction: hasValue ? Math.max(0, Math.min(1, value / maximum)) : 0
    readonly property bool warning: fraction >= 0.8
    readonly property real gauge: 306   // 85 % of the circle, the gap at the bottom

    Item {
        anchors.fill: parent
        readonly property real size: Math.min(width, height)
        Shape {
            id: ring
            width: parent.size
            height: parent.size
            anchors.centerIn: parent
            preferredRendererType: Shape.CurveRenderer
            readonly property real stroke: Math.max(6, width * 0.08)
            readonly property real r: (width - stroke) / 2
            ShapePath {
                strokeColor: "#232b36"
                strokeWidth: ring.stroke
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc {
                    centerX: ring.width / 2; centerY: ring.height / 2
                    radiusX: ring.r; radiusY: ring.r
                    startAngle: 117; sweepAngle: card.gauge
                }
            }
            ShapePath {
                strokeColor: card.hasValue ? card.accent : "transparent"
                strokeWidth: ring.stroke
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathAngleArc {
                    centerX: ring.width / 2; centerY: ring.height / 2
                    radiusX: ring.r; radiusY: ring.r
                    startAngle: 117; sweepAngle: Math.max(0.01, card.gauge * card.fraction)
                }
            }
        }
        Column {
            anchors.centerIn: ring
            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: card.hasValue ? Math.round(card.value) : "--"
                color: card.warning ? "#f87171" : card.textColor
                font.pixelSize: ring.width * 0.26
                font.bold: true
            }
            Label {
                anchors.horizontalCenter: parent.horizontalCenter
                text: card.settings.unit || ""
                color: card.subTextColor
                font.pixelSize: ring.width * 0.11
            }
        }
    }
}
