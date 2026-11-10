# Asynchronous client for the OpenLinkHub HTTP API
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# All requests go through one QNetworkAccessManager, so nothing blocks the UI.
# OpenLinkHub answers {"code": ..., "status": 1 | 0, "message": ..., ...}.
# For changes (POST, PUT) status 1 means success; reads (GET) often answer
# status 0 with their data, so for them code 200 is enough.

import json

from PySide6.QtCore import QByteArray, QObject, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

DEFAULT_URL = "http://127.0.0.1:27003"
TIMEOUT_MS = 8000


class ApiClient(QObject):
    def __init__(self, base_url=DEFAULT_URL, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.manager = QNetworkAccessManager(self)

    def get(self, path, callback):
        """GET path; callback(ok, data, error) with the decoded JSON body."""
        self._send("GET", path, None, callback)

    def post(self, path, body, callback=None):
        self._send("POST", path, body, callback)

    def put(self, path, body, callback=None):
        self._send("PUT", path, body, callback)

    def delete(self, path, body, callback=None):
        self._send("DELETE", path, body, callback)

    def _send(self, method, path, body, callback):
        request = QNetworkRequest(QUrl(self.base_url + path))
        request.setTransferTimeout(TIMEOUT_MS)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        data = QByteArray(json.dumps(body).encode()) if body is not None else QByteArray()
        reply = self.manager.sendCustomRequest(request, method.encode(), data)
        reply.finished.connect(lambda: self._finished(reply, callback, method == "GET"))

    @staticmethod
    def _finished(reply, callback, is_read):
        raw = bytes(reply.readAll())
        network_error = reply.error() != QNetworkReply.NetworkError.NoError
        error_text = reply.errorString()
        reply.deleteLater()
        if callback is None:
            return
        try:
            data = json.loads(raw) if raw else None
        except ValueError:
            data = None
        if network_error and not isinstance(data, dict):
            callback(False, None, error_text)
            return
        if not isinstance(data, dict):
            callback(False, None, "invalid response from OpenLinkHub")
            return
        if data.get("status") == 1 or (is_read and data.get("code") == 200 and not network_error):
            callback(True, data, "")
        else:
            callback(False, data, str(data.get("message") or data.get("data") or "request failed"))
