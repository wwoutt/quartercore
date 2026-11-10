// A single value on the overview
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Frame {
    property string title
    property string value
    property string detail

    Layout.fillWidth: true
    Layout.preferredHeight: 110

    ColumnLayout {
        anchors.fill: parent
        spacing: 2

        Label {
            text: title
            opacity: 0.7
            elide: Text.ElideRight
            Layout.fillWidth: true
        }
        Label {
            text: value
            font.pixelSize: 30
            font.bold: true
        }
        Label {
            text: detail
            visible: detail !== ""
            opacity: 0.6
            font.pixelSize: 12
        }
        Item { Layout.fillHeight: true }
    }
}
