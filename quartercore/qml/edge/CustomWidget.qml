// An own HTML widget (customwidgets/): a web view on the local widget server
// Author: wwoutt (2026-11-10), written by Claude (Anthropic)
// License: GPL-3.0 or later
// Modified by wwoutt, 2026-11-11: shows the widget in a sandboxed web view instead of a placeholder
//
// The page (customwidgets/frame.html) shows widget.html in a sandboxed iframe
// without network access. The view may only show the widget server's pages:
// no other sites, no new windows, no storage on disk.

import QtQuick
import QtQuick.Controls
import QtWebEngine

EdgeCard {
    id: card
    readonly property var manifest: {
        customWidgets.widgets      // again when widgets change
        return customWidgets.widget(card.widget.custom || "")
    }
    readonly property bool known: manifest.id !== undefined

    // Off the record: nothing is written to disk (WebEngineProfilePrototype crashed with PySide6 6.11)
    WebEngineProfile {
        id: privateProfile
        offTheRecord: true
        httpCacheType: WebEngineProfile.MemoryHttpCache
        persistentCookiesPolicy: WebEngineProfile.NoPersistentCookies
    }

    WebEngineView {
        id: view
        visible: card.known && customWidgets.webViews
        anchors.fill: parent
        anchors.margins: -14     // the card's padding is the widget's own
        profile: privateProfile
        backgroundColor: "transparent"
        url: visible ? customWidgets.frameUrl(card.widget.custom) : "about:blank"
        settings.localStorageEnabled: false
        settings.javascriptCanOpenWindows: false
        settings.javascriptCanAccessClipboard: false
        settings.pluginsEnabled: false
        settings.localContentCanAccessRemoteUrls: false
        settings.localContentCanAccessFileUrls: false
        settings.focusOnNavigationEnabled: false
        onNavigationRequested: request => {
            if (!customWidgets.isOwnPage(request.url)) request.reject()
        }
        onNewWindowRequested: request => {}
        onContextMenuRequested: request => request.accepted = true
        onFeaturePermissionRequested: (origin, feature) => grantFeaturePermission(origin, feature, false)
    }

    Label {
        visible: !view.visible
        anchors.centerIn: parent
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        text: !card.known ? qsTr("Own widget \"%1\" is not installed").arg(card.widget.custom || "")
                          : qsTr("Own widgets need QtWebEngine")
        color: card.subTextColor
        font.pixelSize: card.unit
    }
}
