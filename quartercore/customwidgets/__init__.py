# Own XENEON EDGE widgets in HTML, made by anyone, with a widget store
# Author: wwoutt (2026-11-11), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Same widget format as the custom widgets of the fork wwoutt/OpenLinkHub
# (widget.json + widget.html with onData, olhAction and settings), so those
# widgets work here unchanged. Widgets live in ~/.config/Quartercore/widgets/.
#
# library.py  widgets on disk: manifests, settings, data sources, actions
# server.py   local HTTP server the kiosk's web views talk to (token per run)
# store.py    the widget store (reviewed catalog and community repositories)
# manager.py  the CustomWidgets QObject for QML
