// Temperature history of the CPU, GPU or a device sensor
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Shapes

EdgeCard {
    id: card
    title: settings.headerText || ""

    ColumnLayout {
        anchors.fill: parent
        spacing: 6
        RowLayout {
            Label {
                text: (info.value || "--") + " " + (info.unit || "")
                color: card.textColor
                font.pixelSize: Math.min(card.settings.fontSize || 48, card.height * 0.22)
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Column {
                Label { text: qsTr("Min %1").arg(info.min || "--"); color: card.subTextColor; font.pixelSize: card.unit }
                Label { text: qsTr("Max %1").arg(info.max || "--"); color: card.subTextColor; font.pixelSize: card.unit }
            }
        }
        Item {
            id: plot
            Layout.fillWidth: true
            Layout.fillHeight: true
            // The segments are in a 600 x 140 box (like the SVG of the web page)
            Repeater {
                model: info.segments || []
                delegate: Shape {
                    id: segment
                    anchors.fill: parent
                    preferredRendererType: Shape.CurveRenderer
                    readonly property var points: modelData.map(p => Qt.point(p[0] * plot.width / 600, p[1] * plot.height / 140))
                    ShapePath {
                        strokeColor: "transparent"
                        fillColor: Qt.rgba(card.accent.r, card.accent.g, card.accent.b, 0.18)
                        PathPolyline {
                            path: segment.points.length > 0
                                  ? [Qt.point(segment.points[0].x, plot.height)].concat(segment.points,
                                    [Qt.point(segment.points[segment.points.length - 1].x, plot.height)])
                                  : []
                        }
                    }
                    ShapePath {
                        strokeColor: card.accent
                        strokeWidth: 2.5
                        fillColor: "transparent"
                        PathPolyline { path: segment.points }
                    }
                }
            }
        }
    }
}
