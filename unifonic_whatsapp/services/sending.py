"""Outbox. Exactly-one remote delivery cannot be guaranteed without provider idempotency.

We persist Sending before the network call, use unique referenceId, and NEVER blindly
retry an ambiguous HTTP timeout/5xx. Unknown deliveries are reconciled by referenceId.
"""
import json
import secrets
import frappe
from frappe.utils import add_to_date, now_datetime
from unifonic_whatsapp.services.phone import normalize_phone
from unifonic_whatsapp.services.client import UnifonicClient, UnifonicError, extract_message_id
from unifonic_whatsapp.services.consent import has_opt_in
from unifonic_whatsapp.services.conversations import bump, find_or_create


def active_session(conversation):
    if not conversation.last_inbound_at:
        return False
    now = now_datetime()
    boundary = add_to_date(frappe.utils.get_datetime(conversation.last_inbound_at), hours=24)
    return now < boundary and now >= frappe.utils.get_datetime(conversation.last_inbound_at)


def make_text(conversation, text, *, source_doctype=None, source_name=None):
    if not text or len(text) > 4096:
        frappe.throw("Text must contain 1 to 4096 characters")
    if not active_session(conversation):
        frappe.throw("24-hour customer-service window expired. Send an approved template instead.")
    return make_outbox(conversation, "text", {"type": "text", "text": text}, text,
                       source_doctype=source_doctype, source_name=source_name)


def make_template(account, phone, template_name, language, components=None, *,
                  source_doctype=None, source_name=None):
    phone = normalize_phone(phone)
    if not has_opt_in(account, phone):
        frappe.throw("Explicit WhatsApp opt-in is required before business-initiated template messages")
    matches = frappe.get_all("UW Template", filters={"account": account, "template_name": template_name,
                                                       "language": language, "status": "APPROVED"},
                             fields=["name"], limit=1)
    if not matches:
        frappe.throw("Template must be approved and synced for this account/language")
    conversation = find_or_create(account, phone)
    content = {"type": "template", "name": template_name, "language": {"code": language}}
    if components:
        if not isinstance(components, list) or len(json.dumps(components)) > 20000:
            frappe.throw("Template components must be a JSON array <= 20 KB")
        content["components"] = components
    return make_outbox(conversation, "template", content, f"[Template: {template_name}]",
                       source_doctype=source_doctype, source_name=source_name)


def make_outbox(conversation, type_, content, preview, *, source_doctype=None, source_name=None):
    account = frappe.get_doc("UW Account", conversation.account)
    if not account.enabled:
        frappe.throw("Unifonic account is disabled")
    doc = frappe.get_doc({"doctype": "UW Message", "idempotency_key": secrets.token_hex(32),
                          "conversation": conversation.name,
                          "account": account.name, "direction": "Outbound", "message_type": type_,
                          "text": preview, "content_json": json.dumps(content, ensure_ascii=False),
                          "status": "Queued", "source_doctype": source_doctype,
                          "source_name": source_name})
    doc.insert(ignore_permissions=True)
    # Reference must be persisted before dispatch; provider supports referenceId.
    doc.db_set("reference_id", doc.name, update_modified=False)
    bump(conversation, preview)
    frappe.enqueue("unifonic_whatsapp.services.sending.dispatch", queue="short",
                   message_name=doc.name, enqueue_after_commit=True)
    return doc.name


def dispatch(message_name):
    # Claim once via SQL update. Frappe background job executes under a trusted worker.
    msg = frappe.get_doc("UW Message", message_name)
    if msg.direction != "Outbound" or msg.status != "Queued":
        return
    conversation = frappe.get_doc("UW Conversation", msg.conversation)
    account = frappe.get_doc("UW Account", msg.account)
    if not account.enabled:
        frappe.db.set_value("UW Message", msg.name, {"status": "Failed", "error_details": "Account disabled"})
        return
    if msg.message_type == "text" and not active_session(conversation):
        frappe.db.set_value("UW Message", msg.name, {"status": "Failed", "error_details": "Service window expired"})
        return
    if msg.message_type == "template" and not has_opt_in(msg.account, conversation.contact):
        frappe.db.set_value("UW Message", msg.name, {"status": "Failed", "error_details": "Consent withdrawn"})
        return
    if not account.live_sending_enabled:
        frappe.db.set_value("UW Message", msg.name, {"status": "Dry Run"})
        return
    # Single claim for multiple workers, and commit before HTTP to avoid replay after crash.
    frappe.db.sql("UPDATE `tabUW Message` SET status='Sending', attempt_count=attempt_count+1 "
                  "WHERE name=%s AND status='Queued'", msg.name)
    claimed = frappe.db._cursor.rowcount
    if claimed != 1:
        return
    frappe.db.commit()  # intentional: mark external-side-effect boundary
    try:
        content = json.loads(msg.content_json)
        response = UnifonicClient(account).send(conversation.contact, content, msg.reference_id or msg.name)
        provider_id = extract_message_id(response)
        # Preserve newer webhook statuses. Provider events may arrive while POST is in flight.
        current = frappe.db.get_value("UW Message", msg.name, "status")
        updates = {"sent_at": now_datetime(), "error_details": ""}
        if current in ("Sending", "Unknown", "Queued"):
            updates["status"] = "Submitted"
        if provider_id and not frappe.db.get_value("UW Message", msg.name, "external_message_id"):
            updates["external_message_id"] = provider_id
        frappe.db.set_value("UW Message", msg.name, updates)
        frappe.db.commit()
    except UnifonicError as exc:
        current = frappe.db.get_value("UW Message", msg.name, "status")
        if current in ("Sending", "Queued", "Unknown"):
            frappe.db.set_value("UW Message", msg.name, {"status": "Unknown" if exc.uncertain else "Failed",
                                                             "error_details": str(exc)[:250]})
        frappe.db.commit()
    except Exception:
        current = frappe.db.get_value("UW Message", msg.name, "status")
        if current in ("Sending", "Queued", "Unknown"):
            frappe.db.set_value("UW Message", msg.name, {"status": "Unknown",
                                                         "error_details": "Unexpected worker exception; reconcile before retry"})
        frappe.db.commit()
        frappe.log_error(title="Unifonic dispatch failure", message=frappe.get_traceback())
