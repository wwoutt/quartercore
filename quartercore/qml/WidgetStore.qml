// The widget store: own widgets made by others, to install with one click
// Author: wwoutt (2026-11-11), written by Claude (Anthropic)
// License: GPL-3.0 or later
//
// Two tabs, like the store of the fork wwoutt/OpenLinkHub:
// - Reviewed: the catalog wwoutt/quartercore-widgets, files checked by SHA-256
// - Community: GitHub repositories with the topic quartercore-widget, not
//   reviewed, installed at the commit that was previewed
// A widget that runs code shows its code first and needs a confirmation.
// Nothing updates by itself.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: store
    objectName: "widgetStore"
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(parent.width - 48, 980)
    height: Math.min(parent.height - 48, 760)
    modal: true
    title: qsTr("Widget store")
    standardButtons: Dialog.Close

    property string kind: "catalog"
    property var results: []
    property bool busy: false
    property string error: ""
    property var preview: null       // a widget being looked at, with its files
    property bool confirmed: false

    function search() {
        busy = true
        error = ""
        customWidgets.storeList(kind, query.text)
    }
    onOpened: { preview = null; search() }

    Connections {
        target: customWidgets
        function onStoreListed(kind, widgets, error) {
            if (kind !== store.kind) return
            store.busy = false
            store.results = widgets
            store.error = error
        }
        function onStorePreviewed(preview, error) {
            store.busy = false
            store.error = error
            store.confirmed = false
            store.preview = error ? null : preview
        }
        function onStoreDone(what, id, error) {
            store.busy = false
            if (error) {
                store.error = error
                return
            }
            backend.notify(what === "install" ? qsTr("\"%1\" installed: add it with \"Add widget\"").arg(id)
                                              : qsTr("\"%1\" removed").arg(id), true)
            store.preview = null
            store.search()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        // --- list ---
        RowLayout {
            visible: store.preview === null
            Layout.fillWidth: true
            TabBar {
                id: tabs
                TabButton { text: qsTr("Reviewed"); width: implicitWidth }
                TabButton { text: qsTr("Community (not reviewed)"); width: implicitWidth }
                onCurrentIndexChanged: { store.kind = currentIndex === 0 ? "catalog" : "community"; store.search() }
            }
            TextField {
                id: query
                Layout.fillWidth: true
                placeholderText: qsTr("Search…")
                onAccepted: store.search()
            }
            Button { text: qsTr("Search"); icon.name: "search"; onClicked: store.search() }
        }
        Label {
            visible: store.preview === null && store.kind === "community"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#f67400"
            text: qsTr("Community widgets are not reviewed. Only install widgets you trust, and read their code first.")
        }
        Label {
            visible: store.error !== ""
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#da4453"
            text: store.error
        }
        BusyIndicator { visible: store.busy; running: store.busy; Layout.alignment: Qt.AlignHCenter }

        ListView {
            visible: store.preview === null && !store.busy
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            model: store.results
            ScrollBar.vertical: ScrollBar {}
            Label {
                anchors.centerIn: parent
                visible: parent.count === 0 && store.error === ""
                text: qsTr("No widgets found")
                opacity: 0.6
            }
            delegate: Frame {
                required property var modelData
                width: ListView.view.width - 12
                RowLayout {
                    anchors.fill: parent
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        RowLayout {
                            Label { text: modelData.name || modelData.id; font.bold: true }
                            Label { visible: !!modelData.version; text: modelData.version || ""; opacity: 0.6 }
                            Label {
                                visible: modelData.runsCode === true
                                text: qsTr("runs code")
                                color: "#f67400"
                            }
                            Label { visible: !!modelData.installed; text: qsTr("installed"); color: "#27ae60" }
                            Label { visible: !!modelData.update; text: qsTr("update available"); color: "#3daee9" }
                            Label { visible: !!modelData.conflict; text: qsTr("name in use"); color: "#da4453" }
                        }
                        Label {
                            Layout.fillWidth: true
                            text: modelData.description || ""
                            wrapMode: Text.WordWrap
                            opacity: 0.8
                        }
                        Label {
                            text: [modelData.author, modelData.license].filter(t => !!t).join(" · ")
                                  + (modelData.stars !== undefined ? " · ★ " + modelData.stars : "")
                            opacity: 0.6
                            font.pixelSize: 12
                        }
                    }
                    Button {
                        text: modelData.update ? qsTr("Update") : modelData.installed ? qsTr("View") : qsTr("View and install")
                        enabled: !modelData.conflict
                        onClicked: { store.busy = true; store.error = ""; customWidgets.storePreview(store.kind, modelData.ref) }
                    }
                    Button {
                        visible: !!modelData.installed
                        text: qsTr("Remove")
                        icon.name: "edit-delete"
                        onClicked: { store.busy = true; customWidgets.storeUninstall(modelData.id) }
                    }
                }
            }
        }

        // --- preview of one widget ---
        ColumnLayout {
            id: previewPane
            visible: store.preview !== null
            Layout.fillWidth: true
            Layout.fillHeight: true
            readonly property var manifest: store.preview ? store.preview.manifest || {} : ({})
            RowLayout {
                Button { text: qsTr("Back"); icon.name: "go-previous"; onClicked: store.preview = null }
                Label { text: previewPane.manifest.name || ""; font.bold: true; font.pixelSize: 18 }
            }
            Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: previewPane.manifest.description || ""
            }
            Label {
                Layout.fillWidth: true
                visible: store.preview !== null && store.preview.runsCode
                wrapMode: Text.WordWrap
                color: "#f67400"
                text: qsTr("This widget runs code on your computer as your user. Read the code below before you install it.")
            }
            Label {
                Layout.fillWidth: true
                visible: store.preview !== null && (store.preview.skipped || []).length > 0
                text: qsTr("Skipped files: %1").arg(store.preview ? (store.preview.skipped || []).join(", ") : "")
                opacity: 0.7
            }
            TabBar {
                id: files
                Layout.fillWidth: true
                Repeater {
                    model: store.preview ? store.preview.files : []
                    TabButton { text: modelData.name; width: implicitWidth }
                }
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                TextArea {
                    readOnly: true
                    font.family: "monospace"
                    wrapMode: TextEdit.NoWrap
                    textFormat: TextEdit.PlainText
                    readonly property var file: store.preview ? store.preview.files[files.currentIndex] || {} : ({})
                    text: file.text === null || file.text === undefined
                          ? qsTr("(binary file, %1 bytes)").arg(file.size || 0) : file.text
                }
            }
            RowLayout {
                CheckBox {
                    visible: store.preview !== null && store.preview.runsCode
                    text: qsTr("I have read the code and trust this widget")
                    checked: store.confirmed
                    onToggled: store.confirmed = checked
                }
                Item { Layout.fillWidth: true }
                Button {
                    text: qsTr("Install")
                    icon.name: "download"
                    highlighted: true
                    enabled: store.preview !== null && (!store.preview.runsCode || store.confirmed) && !store.busy
                    onClicked: {
                        store.busy = true
                        customWidgets.storeInstall(store.preview.kind, store.preview.ref, store.preview.commit || "",
                                                   store.confirmed)
                    }
                }
            }
        }
    }
}
