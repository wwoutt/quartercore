// Calendar: this month, with buttons for the previous and next month
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    readonly property bool sundayFirst: (settings.weekStart || 0) === 1
    property date today: new Date()
    property int year: today.getFullYear()
    property int month: today.getMonth() + 1
    readonly property var cells: edge.calendar(year, month, sundayFirst)
    Timer { interval: 60000; running: true; repeat: true; onTriggered: card.today = new Date() }

    function step(delta) {
        let m = month + delta, y = year
        if (m < 1) { m = 12; y-- } else if (m > 12) { m = 1; y++ }
        month = m; year = y
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 4
        RowLayout {
            Layout.fillWidth: true
            ToolButton { icon.name: "go-previous"; onClicked: card.step(-1) }
            Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: Qt.locale().standaloneMonthName(card.month - 1) + " " + card.year
                color: card.textColor
                font.pixelSize: card.unit * 1.3
                font.bold: true
            }
            ToolButton { icon.name: "go-next"; onClicked: card.step(1) }
        }
        GridLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            columns: 7
            rowSpacing: 0
            columnSpacing: 0
            Repeater {
                // Locale day 0 is Sunday
                model: 7
                delegate: Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: Qt.locale().dayName((index + (card.sundayFirst ? 0 : 1)) % 7, Locale.ShortFormat)
                    color: card.subTextColor
                    font.pixelSize: card.unit
                }
            }
            Repeater {
                model: card.cells
                delegate: Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 6
                    color: modelData.today ? card.accent : "transparent"
                    Label {
                        anchors.centerIn: parent
                        text: modelData.day
                        color: modelData.today ? "#07090c" : modelData.muted ? "#4b5563"
                             : modelData.weekend ? card.subTextColor : card.textColor
                        font.pixelSize: card.unit * 1.05
                        font.bold: modelData.today
                    }
                }
            }
        }
    }
}
