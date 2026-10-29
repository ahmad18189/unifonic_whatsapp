"""ERPNext: opt-in gated outbound messages driven by explicitly enabled rules.

Do NOT register hooks for arbitrary document events without user-authorized rules.
"""
import json
import frappe
from unifonic_whatsapp.services.consent import has_opt_in
from unifonic_whatsapp.services.sending import make_template


def supported_doctypes():
    """DocTypes whose doc_events call this module; a rule for any other DocType never fires."""
    supported = set()
    for doctype, events in (frappe.get_hooks("doc_events") or {}).items():
        for handlers in events.values():
            handlers = handlers if isinstance(handlers, list) else [handlers]
            if any(str(h).startswith(__name__ + ".") for h in handlers):
                supported.add(doctype)
    return supported


def on_submit(doc, method=None):
    _handle(doc, "On Submit")


def on_cancel(doc, method=None):
    _handle(doc, "On Cancel")


def _handle(doc, trigger):
    if not frappe.db.table_exists("UW Notification Rule"):
        return
    rules = frappe.get_all("UW Notification Rule", filters={"enabled": 1,
        "source_doctype": doc.doctype, "trigger": trigger},
        fields=["name", "account", "template", "phone_field", "parameter_fields_json"])
    for rule in rules:
        try:
            account = frappe.get_doc("UW Account", rule.account)
            # Multi-company guard: a rule for company A must never notify company B.
            if not account.enabled or (account.company and doc.get("company") != account.company):
                continue
            phone = doc.get(rule.phone_field)
            if not phone:
                continue
            # A customer without opt-in is an expected skip, not an error to log.
            if not has_opt_in(rule.account, phone):
                continue
            template = frappe.get_doc("UW Template", rule.template)
            fields = json.loads(rule.parameter_fields_json or "[]")
            components = ([{"type": "body", "parameters": [{"type": "text", "text": str(doc.get(f) or "")}
                           for f in fields]}] if fields else [])
            # frappe.throw queues a message for the ERP user even when caught; mute it so
            # a successful submit does not show a WhatsApp error dialog.
            muted = frappe.flags.mute_messages
            frappe.flags.mute_messages = True
            try:
                make_template(rule.account, phone, template.template_name, template.language,
                              components, source_doctype=doc.doctype, source_name=doc.name)
            finally:
                frappe.flags.mute_messages = muted
        except Exception:
            # Never block posting a financial document because WhatsApp failed.
            frappe.log_error(title=f"Unifonic ERPNext rule {rule.name}", message=frappe.get_traceback())
