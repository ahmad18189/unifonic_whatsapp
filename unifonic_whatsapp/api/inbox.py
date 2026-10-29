"""Frontend endpoints. Every call performs explicit role and record authorization."""
import json
import frappe
from unifonic_whatsapp.services.access import require_agent, require_manager, require_conversation, is_manager
from unifonic_whatsapp.services.phone import normalize_phone
from unifonic_whatsapp.services.sending import make_text, make_template, active_session
from unifonic_whatsapp.services.templates import sync_templates as _sync_templates
from unifonic_whatsapp.services.consent import set_opt_in


@frappe.whitelist(methods=["GET"])
def accounts():
    require_agent()
    return frappe.get_all("UW Account", filters={"enabled": 1},
        fields=["name", "account_label", "company", "default_language"],
        order_by="account_label asc", limit_page_length=200)


@frappe.whitelist(methods=["GET"])
def conversations(account=None, search=None, start=0):
    require_agent()
    filters = {"account": account} if account else {}
    if account and not frappe.db.exists("UW Account", {"name": account, "enabled": 1}):
        frappe.throw("Account not enabled")
    if search:
        search = str(search)[:64]
        filters["contact"] = ["like", f"%{search}%"]
    # Frappe permission_query_conditions is respected by get_list, not get_all.
    rows = frappe.get_list("UW Conversation", filters=filters, fields=[
        "name", "account", "contact", "customer_name", "assigned_to", "status",
        "last_inbound_at", "last_message_at", "last_message_preview"],
        order_by="last_message_at desc, creation desc", start=int(start), page_length=50)
    for row in rows:
        row["session_open"] = bool(active_session(row))
    return rows


@frappe.whitelist(methods=["GET"])
def messages(conversation, start=0):
    require_conversation(conversation)
    return frappe.get_list("UW Message", filters={"conversation": conversation},
        fields=["name", "direction", "message_type", "text", "status", "received_at",
                "sent_at", "creation", "error_details", "content_json"],
        order_by="creation desc", start=int(start), page_length=100)


@frappe.whitelist(methods=["POST"])
def send_text(conversation, text):
    convo = require_conversation(conversation)
    return {"message": make_text(convo, str(text))}


@frappe.whitelist(methods=["POST"])
def send_template(account, phone, template_name, language, components_json="[]"):
    require_agent()
    phone = normalize_phone(phone)
    name = frappe.db.get_value("UW Conversation", {"account": account, "contact": phone}, "name")
    if not is_manager():
        if not name:
            frappe.throw("Only a manager may start a new conversation", frappe.PermissionError)
        require_conversation(name)
    components = json.loads(components_json or "[]")
    return {"message": make_template(account, phone, template_name, language, components)}


@frappe.whitelist(methods=["GET"])
def templates(account):
    require_agent()
    return frappe.get_list("UW Template", filters={"account": account},
        fields=["name", "template_name", "language", "category", "status", "components_json"],
        order_by="template_name asc", page_length=500)


@frappe.whitelist(methods=["POST"])
def sync_templates(account):
    require_manager()
    return {"synced": _sync_templates(account)}


@frappe.whitelist(methods=["POST"])
def assign(conversation, user=None):
    require_manager()
    doc = frappe.get_doc("UW Conversation", conversation)
    if user and not frappe.db.exists("User", {"name": user, "enabled": 1}):
        frappe.throw("Agent is not enabled")
    if user and "Unifonic Agent" not in frappe.get_roles(user) and not is_manager(user):
        frappe.throw("Only an Unifonic agent or manager may be assigned")
    doc.db_set("assigned_to", user or "")
    return {"assigned_to": doc.assigned_to}


@frappe.whitelist(methods=["POST"])
def resolve(conversation, status="Resolved"):
    doc = require_conversation(conversation)
    if status not in ("Open", "Resolved"):
        frappe.throw("Unknown status")
    doc.db_set("status", status)
    return {"status": status}


@frappe.whitelist(methods=["POST"])
def update_consent(account, phone, status, source, evidence):
    require_manager()
    return {"consent": set_opt_in(account, phone, status, source, evidence)}
