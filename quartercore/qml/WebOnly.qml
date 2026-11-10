// A device that has no page in this app yet
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 520)
        spacing: 12

        Label {
            text: backend.active.product || ""
            font.pixelSize: 26
            Layout.alignment: Qt.AlignHCenter
        }
        Label {
            text: qsTr("This device doesn't have a page in Quartercore yet. You can manage it in the OpenLinkHub web interface in the meantime.")
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            opacity: 0.8
            Layout.fillWidth: true
        }
        Button {
            text: qsTr("Open in browser")
            icon.name: "internet-web-browser"
            Layout.alignment: Qt.AlignHCenter
            onClicked: backend.openInBrowser(backend.activeSerial)
        }
    }
}
