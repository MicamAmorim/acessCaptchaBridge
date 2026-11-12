"""Regression checks for persistent, revocable side-panel UX."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "extension"


class SidePanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        cls.background = (ROOT / "background.js").read_text(encoding="utf-8")
        cls.panel = (ROOT / "popup.html").read_text(encoding="utf-8")
        cls.ui = (ROOT / "popup.js").read_text(encoding="utf-8")

    def test_panel_opens_instead_of_ephemeral_popup(self):
        self.assertIn("sidePanel", self.manifest["permissions"])
        self.assertEqual(self.manifest["side_panel"]["default_path"], "popup.html")
        self.assertNotIn("default_popup", self.manifest["action"])
        self.assertIn("openPanelOnActionClick: true", self.background)

    def test_one_time_browser_permission_is_revocable(self):
        self.assertIn("<all_urls>", self.manifest["optional_host_permissions"])
        self.assertIn("chrome.permissions.request(", self.ui)
        self.assertIn("chrome.permissions.contains(", self.ui)
        self.assertIn("chrome.permissions.remove(", self.ui)
        self.assertIn("requirePersistentAccess()", self.background)
        self.assertIn("id=\"revokeCapture\"", self.panel)

    def test_remote_consent_is_scoped_to_site_and_revocable(self):
        self.assertIn("const APPROVAL_KEY = 'codexSiteApprovals'", self.ui)
        self.assertIn("approvals[origin] = true", self.ui)
        self.assertIn("delete approvals[currentOrigin]", self.ui)
        self.assertIn("selected.provider === 'codex' && !remoteGranted", self.ui)
        self.assertIn("id=\"revokeCodex\"", self.panel)

    def test_analysis_remains_manual_and_backend_recovers(self):
        self.assertIn("await call('CAPTURE')", self.ui)
        self.assertIn("await syncPermissions();", self.ui)
        self.assertIn("setInterval(", self.ui)
        self.assertIn("if (current.id !== tab.id || current.url !== tab.url)", self.background)
        self.assertNotIn("id=\"consent\"", self.panel)
        self.assertNotIn("id=\"codexConsent\"", self.panel)


if __name__ == "__main__":
    unittest.main()
