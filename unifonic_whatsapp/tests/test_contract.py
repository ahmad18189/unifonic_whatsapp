import json
import unittest
from pathlib import Path


class TestDocumentedPayloads(unittest.TestCase):
    def test_examples_have_correct_unifonic_contract(self):
        root = Path(__file__).resolve().parents[2] / "examples"
        for name in ("send_text", "send_template"):
            data = json.loads((root / f"{name}.json").read_text())
            self.assertEqual(data["recipient"]["channel"], "whatsapp")
            self.assertIn("referenceId", data)
            self.assertEqual(data["content"]["type"], "text" if name == "send_text" else "template")
        for name in ("webhook_inbound", "webhook_delivered"):
            data = json.loads((root / f"{name}.json").read_text())
            self.assertIn("eventId", data)
            self.assertTrue(data["eventType"].startswith("message."))
            self.assertIn("applicationId", data)
