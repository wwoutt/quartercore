// Memory usage: RAM and swap
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card
    title: settings.headerText || ""

    component Bar: Rectangle {
        property real fraction: 0
        Layout.fillWidth: true
        height: 8; radius: 4; color: "#232b36"
        Rectangle { width: parent.width * Math.max(0, Math.min(1, parent.fraction)); height: parent.height; radius: 4; color: card.accent }
    }

    Label {
        visible: !info.available
        anchors.centerIn: parent
        text: qsTr("Memory data unavailable")
        color: card.subTextColor
        font.pixelSize: card.unit * 1.1
    }
    ColumnLayout {
        visible: !!info.available
        anchors.fill: parent
        spacing: 6
        RowLayout {
            Label { text: qsTr("RAM"); color: card.textColor; font.pixelSize: card.unit * 1.2; Layout.fillWidth: true }
            Label {
                text: (info.percent || 0).toFixed(1) + " %"
                color: card.textColor
                font.pixelSize: Math.min(card.settings.fontSize || 36, card.unit * 2.4)
                font.bold: true
            }
        }
        Bar { fraction: (info.percent || 0) / 100 }
        Label {
            text: qsTr("Used %1 · Total %2 · Available %3").arg(info.used || "").arg(info.total || "").arg(info.free || "")
            color: card.subTextColor
            font.pixelSize: card.unit
            Layout.fillWidth: true
            elide: Text.ElideRight
        }
        Item { Layout.fillHeight: true; visible: !!card.settings.showSwap }
        RowLayout {
            visible: !!card.settings.showSwap
            Label { text: qsTr("Swap"); color: card.textColor; font.pixelSize: card.unit * 1.2; Layout.fillWidth: true }
            Label {
                text: (info.swapTotal || 0) > 0 ? (info.swapPercent || 0).toFixed(1) + " %" : qsTr("No swap")
                color: card.textColor
                font.pixelSize: card.unit * 1.2
                font.bold: true
            }
        }
        Bar { visible: !!card.settings.showSwap && (info.swapTotal || 0) > 0; fraction: (info.swapPercent || 0) / 100 }
        Label {
            visible: !!card.settings.showSwap && (info.swapTotal || 0) > 0
            text: qsTr("Used %1 · Total %2").arg(info.swapUsed || "").arg(info.swapSize || "")
            color: card.subTextColor
            font.pixelSize: card.unit
        }
        Item { Layout.fillHeight: true }
    }
}
