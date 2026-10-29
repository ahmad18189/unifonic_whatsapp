"""ERPNext: opt-in gated outbound messages driven by explicitly enabled rules.

Do NOT register hooks for arbitrary document events without user-authorized rules.
"""
import json
import frappe
from unifonic_whatsapp.services.sending import make_template


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
            template = frappe.get_doc("UW Template", rule.template)
            fields = json.loads(rule.parameter_fields_json or "[]")
            components = ([{"type": "body", "parameters": [{"type": "text", "text": str(doc.get(f) or "")}
                           for f in fields]}] if fields else [])
            make_template(rule.account, phone, template.template_name, template.language,
                          components, source_doctype=doc.doctype, source_name=doc.name)
        except Exception:
            # Never block posting a financial document because WhatsApp failed.
            frappe.log_error(title=f"Unifonic ERPNext rule {rule.name}", message=frappe.get_traceback())
