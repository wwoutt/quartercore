// A colour swatch that opens the colour picker
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

Button {
    id: button
    property color value: "black"
    property string dialogTitle: qsTr("Choose a colour")
    signal picked(color value)

    implicitWidth: 64
    implicitHeight: 36
    ToolTip.visible: hovered
    ToolTip.text: value.toString().toUpperCase()

    contentItem: Rectangle {
        radius: 4
        color: button.value
        border.color: Qt.rgba(1, 1, 1, 0.3)
    }

    onClicked: dialog.open()

    ColorDialog {
        id: dialog
        title: button.dialogTitle
        selectedColor: button.value
        onAccepted: button.picked(selectedColor)
    }
}
