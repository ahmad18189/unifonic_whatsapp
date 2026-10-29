"""Public HTTP webhook only. Do not expose an endpoint without the shared secret.

Unifonic's cited docs do NOT document a signature format. Token authentication is a
compensating control; confirm provider support for signed callbacks before claiming HMAC.
"""
import hashlib
import hmac
import json

import frappe
from frappe.utils import now_datetime
from unifonic_whatsapp.services.events import enqueue_process

MAX_BYTES = 256 * 1024


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
    req = frappe.local.request
    if req.method != "POST":
        frappe.throw("POST only", frappe.PermissionError)
    # Frappe v15 builds form_dict from the JSON body alone and drops the query string,
    # so the callback credentials must be read from the URL args directly.
    account = req.args.get("account")
    token = req.args.get("token")
    if not account or not token:
        frappe.throw("Unauthorized webhook", frappe.PermissionError)
    # Same response for unknown and misconfigured accounts: no account enumeration.
    if not frappe.db.exists("UW Account", account):
        frappe.throw("Unauthorized webhook", frappe.PermissionError)
    settings = frappe.get_doc("UW Account", account)
    expected = settings.get_password("webhook_token", raise_exception=False) or ""
    if not settings.enabled or len(expected) < 32 or not hmac.compare_digest(expected, str(token)):
        frappe.throw("Unauthorized webhook", frappe.PermissionError)
    raw = req.get_data(cache=True)
    if len(raw) > MAX_BYTES:
        frappe.throw("Webhook payload exceeds 256 KB")
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        frappe.throw("Invalid webhook JSON")
    if not isinstance(payload, dict):
        frappe.throw("Webhook must be a JSON object")
    if payload.get("applicationId") != settings.application_id:
        frappe.throw("Application mismatch", frappe.PermissionError)
    event_type = payload.get("eventType")
    if not isinstance(event_type, str) or not event_type.startswith("message."):
        frappe.throw("Unknown event type")
    event_id = payload.get("eventId") or ""
    # Use event ID AND event type as the dedupe key; fallback to canonical raw hash.
    identity = f"{account}|{event_type}|{event_id}" if event_id else (
        f"{account}|{event_type}|{json.dumps(payload,sort_keys=True,ensure_ascii=False)}")
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if not frappe.db.exists("UW Webhook Event", key):
        event = frappe.get_doc({"doctype": "UW Webhook Event", "event_key": key,
            "account": account, "event_id": str(event_id)[:140], "event_type": event_type,
            "external_message_id": payload.get("messageId"),
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "status": "Received", "received_at": now_datetime()})
        try:
            event.insert(ignore_permissions=True)
        except frappe.DuplicateEntryError:
            pass
    enqueue_process(key, after_commit=True)
    return {"received": True}
