"""Unit tests for webhook auth, base URL, poll ordering and ERPNext guards. DB calls are mocked."""
import json
import unittest
from types import SimpleNamespace
from unittest import mock

import frappe

from unifonic_whatsapp.api import webhook
from unifonic_whatsapp.integrations import erpnext
from unifonic_whatsapp.jobs import poll_target
from unifonic_whatsapp.unifonic_whatsapp.doctype.uw_account.uw_account import check_base_url

TOKEN = "t" * 40
APP_ID = "app-123"


def fake_request(args, body=None):
    raw = json.dumps(body or {}).encode()
    return SimpleNamespace(method="POST", args=args, get_data=lambda cache=True: raw)


class TestWebhookAuth(unittest.TestCase):
    def call(self, request):
        with mock.patch.object(frappe.local, "request", request, create=True):
            return webhook.receive()

    def test_missing_query_credentials_rejected(self):
        with self.assertRaises(frappe.PermissionError):
            self.call(fake_request({}))

    def test_unknown_account_rejected_like_bad_token(self):
        with mock.patch.object(frappe.db, "exists", return_value=False):
            with self.assertRaises(frappe.PermissionError):
                self.call(fake_request({"account": "nope", "token": TOKEN}))

    def test_credentials_read_from_query_string_with_json_body(self):
        settings = SimpleNamespace(enabled=1, application_id=APP_ID,
                                   get_password=lambda *a, **k: TOKEN)
        event = mock.MagicMock()

        def get_doc(arg, *args):
            return settings if arg == "UW Account" else event

        body = {"eventId": "e1", "eventType": "message.received", "applicationId": APP_ID}
        with mock.patch.object(frappe.db, "exists", side_effect=[True, False]), \
                mock.patch.object(frappe, "get_doc", side_effect=get_doc), \
                mock.patch.object(webhook, "enqueue_process") as enqueue:
            result = self.call(fake_request({"account": "acc", "token": TOKEN}, body))
        self.assertEqual(result, {"received": True})
        event.insert.assert_called_once()
        enqueue.assert_called_once()

    def test_wrong_token_rejected(self):
        settings = SimpleNamespace(enabled=1, application_id=APP_ID,
                                   get_password=lambda *a, **k: TOKEN)
        with mock.patch.object(frappe.db, "exists", return_value=True), \
                mock.patch.object(frappe, "get_doc", return_value=settings):
            with self.assertRaises(frappe.PermissionError):
                self.call(fake_request({"account": "acc", "token": "x" * 40}))


class TestBaseUrl(unittest.TestCase):
    def test_accepts_https_and_strips_slash(self):
        self.assertEqual(check_base_url("https://apis.unifonic.com/v1/"), "https://apis.unifonic.com/v1")

    def test_rejects_unsafe_urls(self):
        for url in ("http://apis.unifonic.com/v1", "https://user:pw@host/v1",
                    "https://host/v1?x=1", "https://host/v1#f", "apis.unifonic.com", ""):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    check_base_url(url)


class TestPollTarget(unittest.TestCase):
    def test_never_downgrades(self):
        self.assertIsNone(poll_target("Read", "Failed"))
        self.assertIsNone(poll_target("Delivered", "Sent"))
        self.assertIsNone(poll_target("Failed", "Read"))

    def test_upgrades(self):
        self.assertEqual(poll_target("Unknown", "Submitted"), "Submitted")
        self.assertEqual(poll_target("Sending", "Delivered"), "Delivered")
        self.assertEqual(poll_target("Sent", "Failed"), "Failed")


class TestErpnextGuards(unittest.TestCase):
    def test_supported_doctypes_follow_hooks(self):
        hooks = {"Sales Invoice": {"on_submit": ["unifonic_whatsapp.integrations.erpnext.on_submit"]},
                 "Quotation": {"on_submit": ["other_app.handler"]}}
        with mock.patch.object(frappe, "get_hooks", return_value=hooks):
            self.assertEqual(erpnext.supported_doctypes(), {"Sales Invoice"})

    def test_no_opt_in_skips_without_error_or_message(self):
        doc = SimpleNamespace(doctype="Sales Invoice", name="SINV-1",
                              get=lambda f: {"company": "C", "phone": "+966500000001"}.get(f))
        rule = frappe._dict(name="R1", account="acc", template="T1", phone_field="phone",
                            parameter_fields_json="[]")
        with mock.patch.object(frappe.db, "table_exists", return_value=True), \
                mock.patch.object(frappe, "get_all", return_value=[rule]), \
                mock.patch.object(frappe, "get_doc", return_value=SimpleNamespace(enabled=1, company="C")), \
                mock.patch.object(erpnext, "has_opt_in", return_value=False), \
                mock.patch.object(erpnext, "make_template") as make, \
                mock.patch.object(frappe, "log_error") as log:
            erpnext.on_submit(doc)
        make.assert_not_called()
        log.assert_not_called()

    def test_template_errors_are_muted_and_logged(self):
        doc = SimpleNamespace(doctype="Sales Invoice", name="SINV-1",
                              get=lambda f: {"company": "C", "phone": "+966500000001"}.get(f))
        rule = frappe._dict(name="R1", account="acc", template="T1", phone_field="phone",
                            parameter_fields_json="[]")
        seen = {}

        def make_template(*args, **kwargs):
            seen["muted"] = frappe.flags.mute_messages
            raise frappe.ValidationError("Template must be approved")

        def get_doc(doctype, name):
            if doctype == "UW Account":
                return SimpleNamespace(enabled=1, company="C")
            return SimpleNamespace(template_name="t", language="en")

        frappe.flags.mute_messages = False
        with mock.patch.object(frappe.db, "table_exists", return_value=True), \
                mock.patch.object(frappe, "get_all", return_value=[rule]), \
                mock.patch.object(frappe, "get_doc", side_effect=get_doc), \
                mock.patch.object(erpnext, "has_opt_in", return_value=True), \
                mock.patch.object(erpnext, "make_template", side_effect=make_template), \
                mock.patch.object(frappe, "log_error") as log:
            erpnext.on_submit(doc)
        self.assertTrue(seen["muted"])
        self.assertFalse(frappe.flags.mute_messages)
        log.assert_called_once()
