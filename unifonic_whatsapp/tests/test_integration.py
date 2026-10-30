"""Bench integration tests for docs/ACCEPTANCE_TESTS.md cases that need no live provider.

Provider HTTP is always mocked; nothing here can reach Unifonic.
"""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, add_to_date, now_datetime

from unifonic_whatsapp import jobs
from unifonic_whatsapp.api import inbox, webhook
from unifonic_whatsapp.services import events, sending
from unifonic_whatsapp.services.client import UnifonicError
from unifonic_whatsapp.services.consent import set_opt_in
from unifonic_whatsapp.services.conversations import find_or_create

TOKEN = "w" * 40
PHONE = "+966500000001"
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def make_account(app_id, **extra):
    return frappe.get_doc({"doctype": "UW Account", "account_label": app_id, "application_id": app_id,
                           "public_id": "pub", "api_secret": "s" * 20, "webhook_token": TOKEN,
                           "enabled": 1, **extra}).insert(ignore_permissions=True)


def make_user(email, role):
    if not frappe.db.exists("User", email):
        frappe.get_doc({"doctype": "User", "email": email, "first_name": email.split("@")[0],
                        "send_welcome_email": 0, "roles": [{"role": role}]}).insert(ignore_permissions=True)
    return email


def post(account, body, token=TOKEN):
    """Call the webhook the way Frappe does for a JSON body; returns the event key or raises."""
    raw = json.dumps(body).encode()
    request = SimpleNamespace(method="POST", args={"account": account, "token": token},
                              get_data=lambda cache=True: raw)
    with mock.patch.object(frappe.local, "request", request, create=True), \
            mock.patch.object(webhook, "enqueue_process") as enqueue:
        webhook.receive()
    key = enqueue.call_args.args[0]
    events.process(key)
    return key


def inbound(app_id, event_id, message_id, phone=PHONE, text="Hello"):
    body = json.loads((EXAMPLES / "webhook_inbound.json").read_text())
    body.update({"applicationId": app_id, "eventId": event_id, "messageId": message_id,
                 "timestamp": now_datetime().isoformat()})
    body["sender"]["contact"] = phone
    body["content"]["text"] = text
    return body


class UWTestCase(FrappeTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        self.account = make_account("app-a")

    def tearDown(self):
        frappe.set_user("Administrator")
        # FrappeTestCase only rolls back per class; isolate every test.
        frappe.db.rollback()


class TestWebhookIngest(UWTestCase):
    def count(self, doctype, **filters):
        return frappe.db.count(doctype, filters)

    def test_at03_bad_or_missing_token_stores_nothing(self):
        body = inbound("app-a", "e1", "m1")
        for token in ("", "x" * 40):
            with self.subTest(token=token), self.assertRaises(frappe.PermissionError):
                post(self.account.name, body, token=token)
        self.assertEqual(self.count("UW Webhook Event", account=self.account.name), 0)

    def test_at04_other_application_id_rejected(self):
        with self.assertRaises(frappe.PermissionError):
            post(self.account.name, inbound("app-other", "e1", "m1"))
        self.assertEqual(self.count("UW Webhook Event", account=self.account.name), 0)

    def test_at05_replayed_event_is_stored_once(self):
        body = inbound("app-a", "e1", "m1")
        post(self.account.name, body)
        post(self.account.name, body)
        self.assertEqual(self.count("UW Webhook Event", account=self.account.name), 1)
        self.assertEqual(self.count("UW Message", account=self.account.name, direction="Inbound"), 1)

    def test_at06_two_events_same_contact_share_conversation(self):
        post(self.account.name, inbound("app-a", "e1", "m1"))
        post(self.account.name, inbound("app-a", "e2", "m2"))
        self.assertEqual(self.count("UW Conversation", account=self.account.name), 1)
        self.assertEqual(self.count("UW Message", account=self.account.name), 2)

    def test_at07_same_phone_other_account_is_separate(self):
        other = make_account("app-b")
        post(self.account.name, inbound("app-a", "e1", "m1"))
        post(other.name, inbound("app-b", "e1", "m1"))
        self.assertEqual(self.count("UW Conversation", contact=PHONE,
                                    account=["in", [self.account.name, other.name]]), 2)

    def test_inbound_opens_service_window(self):
        post(self.account.name, inbound("app-a", "e1", "m1"))
        convo = frappe.get_doc("UW Conversation", {"conversation_key": f"{self.account.name}|{PHONE}"})
        self.assertTrue(sending.active_session(convo))


class TestDeliveryOrdering(UWTestCase):
    def outbound(self, status="Submitted"):
        convo = find_or_create(self.account.name, PHONE)
        doc = frappe.get_doc({"doctype": "UW Message", "idempotency_key": frappe.generate_hash(),
                              "conversation": convo.name, "account": self.account.name,
                              "direction": "Outbound", "message_type": "text", "text": "x",
                              "status": status, "external_message_id": "out-1"}).insert(ignore_permissions=True)
        return doc.name

    def status_event(self, event_type, event_id):
        body = json.loads((EXAMPLES / "webhook_delivered.json").read_text())
        body.update({"applicationId": "app-a", "eventType": event_type, "eventId": event_id,
                     "messageId": "out-1"})
        return body

    def test_at15_delivered_not_downgraded_by_sent(self):
        name = self.outbound()
        post(self.account.name, self.status_event("message.delivered", "d1"))
        post(self.account.name, self.status_event("message.sent", "s1"))
        self.assertEqual(frappe.db.get_value("UW Message", name, "status"), "Delivered")

    def test_at16_read_not_replaced_by_rejected(self):
        name = self.outbound()
        post(self.account.name, self.status_event("message.read", "r1"))
        post(self.account.name, self.status_event("message.rejected", "x1"))
        self.assertEqual(frappe.db.get_value("UW Message", name, "status"), "Read")

    def test_unmatched_status_is_pending_match(self):
        key = post(self.account.name, self.status_event("message.delivered", "d1"))
        self.assertEqual(frappe.db.get_value("UW Webhook Event", key, "status"), "Pending Match")


class TestAccess(UWTestCase):
    def setUp(self):
        super().setUp()
        self.agent_a = make_user("uw-agent-a@example.com", "Unifonic Agent")
        self.agent_b = make_user("uw-agent-b@example.com", "Unifonic Agent")
        self.manager = make_user("uw-manager@example.com", "Unifonic Manager")
        self.convo = find_or_create(self.account.name, PHONE)
        self.convo.db_set("assigned_to", self.agent_a)

    def test_at09_only_assignee_and_manager_read_messages(self):
        frappe.set_user(self.agent_b)
        with self.assertRaises(frappe.PermissionError):
            inbox.messages(self.convo.name)
        self.assertNotIn(self.convo.name, [r.name for r in inbox.conversations(self.account.name)])
        for user in (self.agent_a, self.manager):
            frappe.set_user(user)
            inbox.messages(self.convo.name)
            self.assertIn(self.convo.name, [r.name for r in inbox.conversations(self.account.name)])

    def test_agent_cannot_start_new_conversation(self):
        frappe.set_user(self.agent_a)
        with self.assertRaises(frappe.PermissionError):
            inbox.send_template(self.account.name, "+966500000099", "t", "en")


class TestOutbox(UWTestCase):
    def setUp(self):
        super().setUp()
        self.convo = find_or_create(self.account.name, PHONE)
        frappe.get_doc({"doctype": "UW Template", "account": self.account.name, "template_name": "t_ok",
                        "language": "en", "status": "APPROVED"}).insert(ignore_permissions=True)
        frappe.get_doc({"doctype": "UW Template", "account": self.account.name, "template_name": "t_pending",
                        "language": "en", "status": "PENDING"}).insert(ignore_permissions=True)

    def opt_in(self, status="Opted In"):
        set_opt_in(self.account.name, PHONE, status, "test", "integration test evidence")

    def set_inbound(self, hours_ago):
        self.convo.db_set("last_inbound_at", add_to_date(now_datetime(), hours=-hours_ago))
        self.convo.reload()

    def test_at10_reply_inside_window_is_queued(self):
        self.set_inbound(1)
        with mock.patch.object(frappe, "enqueue") as enqueue:
            name = sending.make_text(self.convo, "Hi")
        self.assertEqual(frappe.db.get_value("UW Message", name, "status"), "Queued")
        enqueue.assert_called_once()

    def test_at11_reply_after_window_blocked(self):
        self.set_inbound(25)
        with self.assertRaises(frappe.ValidationError):
            sending.make_text(self.convo, "Hi")

    def test_at12_template_without_opt_in_blocked(self):
        with self.assertRaises(frappe.ValidationError):
            sending.make_template(self.account.name, PHONE, "t_ok", "en")

    def test_at13_unapproved_or_wrong_language_blocked(self):
        self.opt_in()
        for name, lang in (("t_pending", "en"), ("t_ok", "ar")):
            with self.subTest(name=name, lang=lang), self.assertRaises(frappe.ValidationError):
                sending.make_template(self.account.name, PHONE, name, lang)

    def test_at14_template_queued_with_reference_id(self):
        self.opt_in()
        with mock.patch.object(frappe, "enqueue"):
            name = sending.make_template(self.account.name, PHONE, "t_ok", "en")
        msg = frappe.get_doc("UW Message", name)
        self.assertEqual((msg.status, msg.reference_id), ("Queued", name))


class TestDispatch(UWTestCase):
    """dispatch() commits by design; commits are patched out so the test transaction rolls back."""

    def setUp(self):
        super().setUp()
        self.account.db_set("live_sending_enabled", 1)
        self.convo = find_or_create(self.account.name, PHONE)
        self.convo.db_set("last_inbound_at", now_datetime())
        with mock.patch.object(frappe, "enqueue"):
            self.name = sending.make_text(self.convo, "Hi")

    def dispatch(self, send):
        client = mock.MagicMock()
        client.send.side_effect = send
        with mock.patch.object(sending, "UnifonicClient", return_value=client), \
                mock.patch.object(frappe.db, "commit"):
            sending.dispatch(self.name)
        return client

    def status(self):
        return frappe.db.get_value("UW Message", self.name, ["status", "external_message_id"])

    def test_success_records_provider_id(self):
        self.dispatch(lambda *a: {"data": {"messageId": "prov-1"}})
        self.assertEqual(self.status(), ("Submitted", "prov-1"))

    def test_at18_second_dispatch_never_posts_again(self):
        first = self.dispatch(lambda *a: {"messageId": "prov-1"})
        second = self.dispatch(lambda *a: {"messageId": "prov-2"})
        self.assertEqual((first.send.call_count, second.send.call_count), (1, 0))

    def test_claim_update_reports_one_row_once(self):
        sql = "UPDATE `tabUW Message` SET status='Sending' WHERE name=%s AND status='Queued'"
        frappe.db.sql(sql, self.name)
        self.assertEqual(frappe.db._cursor.rowcount, 1)
        frappe.db.sql(sql, self.name)
        self.assertEqual(frappe.db._cursor.rowcount, 0)

    def test_at19_timeout_marks_unknown_without_retry(self):
        def timeout(*a):
            raise UnifonicError("Network error; delivery is uncertain", uncertain=True)
        first = self.dispatch(timeout)
        self.assertEqual(self.status()[0], "Unknown")
        second = self.dispatch(timeout)
        self.assertEqual((first.send.call_count, second.send.call_count), (1, 0))
        self.assertEqual(self.status()[0], "Unknown")

    def test_at21_auth_error_fails_without_secret(self):
        def denied(*a):
            raise UnifonicError("Unifonic HTTP 401", 401, False)
        self.dispatch(denied)
        status, error = frappe.db.get_value("UW Message", self.name, ["status", "error_details"])
        self.assertEqual(status, "Failed")
        self.assertNotIn("s" * 20, error)

    def test_live_sending_off_is_dry_run(self):
        self.account.db_set("live_sending_enabled", 0)
        client = self.dispatch(lambda *a: {})
        self.assertEqual(self.status()[0], "Dry Run")
        client.send.assert_not_called()

    def test_at29_opt_out_before_dispatch_blocks_template(self):
        frappe.get_doc({"doctype": "UW Template", "account": self.account.name, "template_name": "t_ok",
                        "language": "en", "status": "APPROVED"}).insert(ignore_permissions=True)
        set_opt_in(self.account.name, PHONE, "Opted In", "test", "evidence")
        with mock.patch.object(frappe, "enqueue"):
            self.name = sending.make_template(self.account.name, PHONE, "t_ok", "en")
        set_opt_in(self.account.name, PHONE, "Opted Out", "test", "customer replied STOP")
        client = self.dispatch(lambda *a: {})
        self.assertEqual(frappe.db.get_value("UW Message", self.name, "error_details"), "Consent withdrawn")
        client.send.assert_not_called()


class TestJobs(UWTestCase):
    def test_at27_purge_keeps_unprocessed_events(self):
        old = add_days(now_datetime(), -31)
        for key, status in (("old-done", "Processed"), ("old-failed", "Failed")):
            frappe.get_doc({"doctype": "UW Webhook Event", "event_key": key, "account": self.account.name,
                            "event_type": "message.received", "payload_json": "{}", "status": status,
                            "received_at": old}).insert(ignore_permissions=True)
        jobs.purge_old_events()
        self.assertFalse(frappe.db.exists("UW Webhook Event", "old-done"))
        self.assertTrue(frappe.db.exists("UW Webhook Event", "old-failed"))

    def test_event_job_is_deduplicated(self):
        from frappe.utils.background_jobs import create_job_id, get_queue, is_job_enqueued
        from rq.job import Job
        # Unique per run: a leftover job record would make both enqueues no-ops.
        name = f"dedupe-{frappe.generate_hash(length=10)}"
        events.enqueue_process(name)
        events.enqueue_process(name)
        queue = get_queue("short")
        job_id = create_job_id(f"uw_event::{name}")
        try:
            self.assertTrue(is_job_enqueued(f"uw_event::{name}"))
            self.assertEqual(queue.job_ids.count(job_id), 1)
        finally:
            # delete(), not queue.remove(): remove() leaves the job record marked queued.
            Job.fetch(job_id, connection=queue.connection).delete()

    def test_locking_read_supported(self):
        convo = find_or_create(self.account.name, PHONE)
        found = frappe.db.get_value("UW Conversation", {"conversation_key": convo.conversation_key},
                                    "name", for_update=True)
        self.assertEqual(found, convo.name)

    def test_workspace_installed_and_links_resolve(self):
        ws = frappe.get_doc("Workspace", "Unifonic WhatsApp")
        targets = [l.link_to for l in ws.links if l.type == "Link"]
        targets += [s.link_to for s in ws.shortcuts if s.type == "DocType"]
        self.assertTrue(targets)
        for doctype in targets:
            self.assertTrue(frappe.db.exists("DocType", doctype), doctype)

    def test_base_url_change_needs_live_sending_off(self):
        self.account.live_sending_enabled = 1
        self.account.api_base_url = "https://sandbox.example.test/v1"
        with self.assertRaises(frappe.ValidationError):
            self.account.save(ignore_permissions=True)
