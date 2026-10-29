import frappe
from frappe.utils import now_datetime
from unifonic_whatsapp.services.phone import normalize_phone


def find_or_create(account, phone, name=None):
    phone = normalize_phone(phone)
    key = f"{account}|{phone}"
    found = frappe.db.get_value("UW Conversation", {"conversation_key": key}, "name")
    if found:
        return frappe.get_doc("UW Conversation", found)
    doc = frappe.get_doc({"doctype": "UW Conversation", "account": account,
                          "conversation_key": key, "contact": phone, "customer_name": name,
                          "status": "Open"})
    try:
        doc.insert(ignore_permissions=True)
        return doc
    except frappe.DuplicateEntryError:
        found = frappe.db.get_value("UW Conversation", {"conversation_key": key}, "name")
        if not found:
            raise
        return frappe.get_doc("UW Conversation", found)


def bump(conversation, preview, timestamp=None, inbound=False, external_conversation_id=None):
    timestamp = timestamp or now_datetime()
    updates = {}
    if not conversation.last_message_at or frappe.utils.get_datetime(timestamp) >= frappe.utils.get_datetime(conversation.last_message_at):
        updates.update({"last_message_at": timestamp, "last_message_preview": (preview or "")[:140]})
    if inbound:
        # Never shorten an active window for an out-of-order incoming event.
        prev = conversation.last_inbound_at
        if not prev or frappe.utils.get_datetime(timestamp) > frappe.utils.get_datetime(prev):
            updates["last_inbound_at"] = timestamp
        updates["status"] = "Open"
    if external_conversation_id:
        updates["external_conversation_id"] = external_conversation_id
    frappe.db.set_value("UW Conversation", conversation.name, updates, update_modified=False)
