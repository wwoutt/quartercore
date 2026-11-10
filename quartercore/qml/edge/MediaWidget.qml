// Media player: what plays now, with the media buttons
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

EdgeCard {
    id: card

    ColumnLayout {
        anchors.fill: parent
        spacing: 6
        Label {
            Layout.fillWidth: true
            text: info.available ? info.title : qsTr("Nothing is playing")
            color: card.textColor
            font.pixelSize: card.unit * 1.8
            font.bold: true
            elide: Text.ElideRight
        }
        Label {
            Layout.fillWidth: true
            visible: !!info.available
            text: info.artist || ""
            color: card.subTextColor
            font.pixelSize: card.unit * 1.2
            elide: Text.ElideRight
        }
        Item { Layout.fillHeight: true }
        Rectangle {
            Layout.fillWidth: true
            height: 6
            radius: 3
            color: "#232b36"
            Rectangle { width: parent.width * (info.progress || 0); height: parent.height; radius: 3; color: card.accent }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: info.position || "0:00"; color: card.subTextColor; font.pixelSize: card.unit }
            Item { Layout.fillWidth: true }
            Label { text: info.length || "0:00"; color: card.subTextColor; font.pixelSize: card.unit }
        }
        RowLayout {
            visible: !card.settings.hideControls
            Layout.alignment: Qt.AlignHCenter
            spacing: 10
            Repeater {
                model: [["previous", "media-skip-backward"], ["stop", "media-playback-stop"],
                        ["play", "media-playback-start"], ["next", "media-skip-forward"],
                        ["volumeDown", "audio-volume-low"], ["volumeUp", "audio-volume-high"],
                        ["mute", "audio-volume-muted"]]
                delegate: RoundButton {
                    icon.name: modelData[1]
                    icon.width: card.unit * 1.6
                    icon.height: card.unit * 1.6
                    onClicked: edge.media(modelData[0])
                }
            }
        }
    }
}
