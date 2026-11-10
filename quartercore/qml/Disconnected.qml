// Shown while OpenLinkHub can't be reached
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

        BusyIndicator { Layout.alignment: Qt.AlignHCenter }
        Label {
            text: qsTr("Connecting to OpenLinkHub…")
            font.pixelSize: 20
            Layout.alignment: Qt.AlignHCenter
        }
        Label {
            text: qsTr("Is the OpenLinkHub service running at %1?").arg(backend.serverUrl)
                  + (backend.error !== "" ? "\n" + backend.error : "")
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            opacity: 0.7
            Layout.fillWidth: true
        }
    }
}
