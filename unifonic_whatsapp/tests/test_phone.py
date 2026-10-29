import unittest
from unifonic_whatsapp.services.phone import normalize_phone


class TestPhone(unittest.TestCase):
    def test_valid_e164(self):
        self.assertEqual(normalize_phone("  +966500000001  "), "+966500000001")

    def test_invalid_numbers(self):
        for text in ("0500000001", "00966500000001", "966500000001", "", " +", "+120", "whatsapp:+966500000001"):
            with self.subTest(phone=text):
                with self.assertRaises(ValueError):
                    normalize_phone(text)
