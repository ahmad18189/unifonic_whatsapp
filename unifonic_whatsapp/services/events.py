"""Inbound message + delivery event processor. All external writes are event-driven."""
import json
import hashlib
import frappe
from frappe.utils import now_datetime
from unifonic_whatsapp.services.conversations import find_or_create, bump
from unifonic_whatsapp.services.timeutil import provider_time
from unifonic_whatsapp.services.phone import normalize_phone

RANK = {"Queued": 0, "Sending": 1, "Submitted": 2, "Sent": 3, "Delivered": 4, "Read": 5}
STATUS_EVENTS = {
    "message.sent": "Sent",
    "message.sent_successfully_to_provider": "Sent",
    "message.delivered": "Delivered",
    "message.read": "Read",
    "message.rejected": "Failed",
    "message.failed": "Failed",
}


def process(event_name):
    event = frappe.get_doc("UW Webhook Event", event_name)
    if event.status == "Processed" or (event.attempts or 0) >= 8:
        return
    frappe.db.savepoint("unifonic_process_event")
    try:
        payload = json.loads(event.payload_json)
        if event.event_type == "message.received":
            incoming(event.account, payload)
            status = "Processed"
        elif event.event_type in STATUS_EVENTS:
            status = "Processed" if delivery(event.account, payload) else "Pending Match"
        elif event.event_type == "message.template_status_update":
            template_status(event.account, payload)
            status = "Processed"
        else:
            # Other account/quality events retained for audit, no downstream mutation.
            status = "Processed"
        event.db_set({"status": status, "attempts": (event.attempts or 0) + 1,
                      "error_details": "", "processed_at": now_datetime() if status == "Processed" else None})
    except Exception:
        frappe.db.rollback(save_point="unifonic_process_event")
        event.db_set({"status": "Failed", "attempts": (event.attempts or 0) + 1,
                      "error_details": "Error during event processing; see server logs"})
        frappe.log_error(title="Unifonic event processing", message=frappe.get_traceback())


def incoming(account, payload):
    sender = payload.get("sender") or {}
    if sender.get("channel") != "whatsapp":
        return
    message_id = payload.get("messageId")
    if not message_id:
        raise ValueError("Incoming event missing messageId")
    phone = normalize_phone(sender.get("contact"))
    dedupe_key = hashlib.sha256(f"{account}|inbound|{message_id}".encode()).hexdigest()
    existing = frappe.db.get_value("UW Message", {"idempotency_key": dedupe_key}, "name")
    if existing:
        return
    convo = find_or_create(account, phone, sender.get("name"))
    content = payload.get("content") or {}
    kind = content.get("type") or "other"
    allowed = {"text", "image", "file", "audio", "video", "location", "option", "sticker"}
    kind = kind if kind in allowed else "other"
    text = content.get("text") or ""
    if not text and kind != "text":
        text = f"[{kind}]"
    message = frappe.get_doc({"doctype": "UW Message", "idempotency_key": dedupe_key,
        "account": account,
        "conversation": convo.name, "direction": "Inbound", "message_type": kind,
        "external_message_id": message_id, "text": str(text)[:20000],
        "content_json": json.dumps(content, ensure_ascii=False), "status": "Received",
        "received_at": provider_time(payload.get("timestamp"))})
    try:
        message.insert(ignore_permissions=True)
    except frappe.DuplicateEntryError:
        return  # Another worker inserted this exact provider message first.
    when = provider_time(payload.get("timestamp"))
    bump(convo, text, timestamp=when, inbound=True,
         external_conversation_id=payload.get("conversationId"))


def delivery(account, payload):
    message_id = payload.get("messageId")
    reference_id = payload.get("referenceId")
    name = None
    if message_id:
        name = frappe.db.get_value("UW Message", {"account": account, "direction": "Outbound",
                                                  "external_message_id": message_id}, "name")
    if not name and reference_id:
        name = frappe.db.get_value("UW Message", {"account": account, "direction": "Outbound",
                                                  "reference_id": reference_id}, "name")
    if not name:
        return False
    message = frappe.get_doc("UW Message", name)
    target = STATUS_EVENTS[payload["eventType"]]
    # Ignore late/out-of-order downgrades. Failed must not replace known Delivered/Read.
    if message.status in ("Delivered", "Read") and target == "Failed":
        return True
    if target in RANK and message.status in RANK and RANK[target] < RANK[message.status]:
        return True
    changes = {"status": target}
    if message_id and not message.external_message_id:
        changes["external_message_id"] = message_id
    if target == "Failed":
        changes["error_details"] = str(payload.get("failReason") or "Provider rejected")[:250]
    frappe.db.set_value("UW Message", name, changes)
    return True


def template_status(account, payload):
    name = payload.get("messageTemplateName")
    if not name:
        return
    template_id = payload.get("messageTemplateId")
    filters = ({"account": account, "provider_template_id": str(template_id)} if template_id
               else {"account": account, "template_name": name})
    rows = frappe.get_all("UW Template", filters=filters,
                          pluck="name", limit_page_length=100)
    for row in rows:
        frappe.db.set_value("UW Template", row, "status", payload.get("status") or "UNKNOWN")
