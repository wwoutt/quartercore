# Tests for settings, autostart and translations
# Author: wwoutt (2026-11-10), written by Claude (Anthropic)
# License: GPL-3.0 or later
#
# Run: python3 -m unittest discover -s tests

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QSettings  # noqa: E402

from quartercore import i18n  # noqa: E402
from quartercore.settings import Settings, autostart_file  # noqa: E402


def source_texts():
    """Every text the interface translates: qsTr("...") in QML, tr("...") and N_("...") in Python."""
    texts = set()
    pattern = re.compile(r'(?:qsTr|tr|N_)\("((?:[^"\\]|\\.)*)"\)')
    for path in list((ROOT / "quartercore").rglob("*.qml")) + list((ROOT / "quartercore").rglob("*.py")):
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            texts.add(match.group(1).replace('\\"', '"').replace("\\'", "'"))
    return texts


class SettingsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XDG_CONFIG_HOME"] = self.tmp.name
        QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, self.tmp.name)
        self.settings = Settings()
        self.settings.store.clear()

    def tearDown(self):
        del os.environ["XDG_CONFIG_HOME"]
        self.tmp.cleanup()

    def test_defaults(self):
        self.assertEqual(self.settings.serverUrl, "http://127.0.0.1:27003")
        self.assertEqual(self.settings.language, "system")
        self.assertTrue(self.settings.closeToTray)
        self.assertFalse(self.settings.autostart)

    def test_server_url_is_cleaned(self):
        self.settings.serverUrl = "  http://example.test:27003/ "
        self.assertEqual(Settings().serverUrl, "http://example.test:27003")
        self.settings.serverUrl = ""
        self.assertEqual(self.settings.serverUrl, "http://127.0.0.1:27003")

    def test_booleans_survive_a_restart(self):
        self.settings.closeToTray = False
        self.assertFalse(Settings().closeToTray)

    def test_autostart_entry(self):
        self.settings.autostart = True
        path = autostart_file()
        self.assertTrue(str(path).startswith(self.tmp.name))
        text = path.read_text()
        self.assertIn("Exec=", text)
        self.assertIn("--minimized", text)
        self.settings.startMinimized = False
        self.assertNotIn("--minimized", path.read_text())
        self.settings.autostart = False
        self.assertFalse(path.exists())


class TranslationTest(unittest.TestCase):
    def test_every_text_has_a_dutch_translation(self):
        missing = sorted(source_texts() - set(i18n.load("nl")))
        self.assertEqual(missing, [], "add these to quartercore/i18n/nl.json")

    def test_no_unused_translations(self):
        unused = sorted(set(i18n.load("nl")) - source_texts())
        self.assertEqual(unused, [], "remove these from quartercore/i18n/nl.json")

    def test_placeholders_are_kept(self):
        for source, text in i18n.load("nl").items():
            self.assertEqual(sorted(re.findall(r"%\d", source)), sorted(re.findall(r"%\d", text)), source)

    def test_translator(self):
        translator = i18n.JsonTranslator()
        translator.set_language("nl")
        self.assertEqual(translator.translate("Main", "Settings"), "Instellingen")
        # Not translated: a null string, so Qt keeps the English text
        self.assertIsNone(translator.translate("Main", "Unknown text"))
        translator.set_language("en")
        self.assertTrue(translator.isEmpty())

    def test_untranslated_text_stays_english(self):
        app = QCoreApplication.instance() or QCoreApplication([])
        translator = i18n.JsonTranslator()
        translator.set_language("en")
        app.installTranslator(translator)
        try:
            self.assertEqual(QCoreApplication.translate("Main", "Settings"), "Settings")
            translator.set_language("nl")
            self.assertEqual(QCoreApplication.translate("Main", "Settings"), "Instellingen")
            self.assertEqual(QCoreApplication.translate("Main", "Not in the list"), "Not in the list")
        finally:
            app.removeTranslator(translator)

    def test_resolve(self):
        self.assertEqual(i18n.resolve("nl"), "nl")
        self.assertIn(i18n.resolve("system"), i18n.LANGUAGES)


if __name__ == "__main__":
    unittest.main()
