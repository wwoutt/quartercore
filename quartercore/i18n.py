# Translations without compiled .qm files
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# The interface is written in English (qsTr in QML, tr in Python). Each
# translation is a JSON file in i18n/ mapping the English text to the
# translated text, so it can be edited without Qt's lrelease tool.
# To add a language: copy i18n/nl.json to i18n/<code>.json and add it to
# LANGUAGES.

import json
from pathlib import Path

from PySide6.QtCore import QLocale, QTranslator

DIR = Path(__file__).resolve().parent / "i18n"
LANGUAGES = {"en": "English", "nl": "Nederlands"}


def resolve(language):
    """The language code to use for a setting ("system", "en", "nl", ...)."""
    if language in LANGUAGES:
        return language
    system = QLocale.system().name().split("_")[0]
    return system if system in LANGUAGES else "en"


def load(code):
    path = DIR / (code + ".json")
    if code == "en" or not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return {k: v for k, v in json.load(f).items() if not k.startswith("_")}


class JsonTranslator(QTranslator):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.texts = {}

    def set_language(self, code):
        self.texts = load(code)

    def translate(self, context, source, disambiguation=None, n=-1):
        # None (a null string) means "not translated", so Qt shows the English
        # text; an empty string would replace it with nothing
        return self.texts.get(source)

    def isEmpty(self):
        return not self.texts
