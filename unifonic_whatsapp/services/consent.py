import frappe
from unifonic_whatsapp.services.phone import normalize_phone


def has_opt_in(account, phone):
    phone = normalize_phone(phone)
    return frappe.db.get_value("UW Consent", {"consent_key": f"{account}|{phone}"}, "status") == "Opted In"


def set_opt_in(account, phone, status, source, evidence):
    from frappe.utils import now_datetime
    from unifonic_whatsapp.services.access import require_manager
    require_manager()
    phone = normalize_phone(phone)
    if status not in ("Opted In", "Opted Out"):
        frappe.throw("Unsupported consent state")
    if not source or not evidence:
        frappe.throw("Consent evidence is required")
    key = f"{account}|{phone}"
    name = frappe.db.get_value("UW Consent", {"consent_key": key}, "name")
    doc = frappe.get_doc("UW Consent", name) if name else frappe.new_doc("UW Consent")
    doc.update({"account": account, "contact": phone, "consent_key": key, "status": status,
                "source": source, "evidence": evidence, "consent_at": now_datetime(),
                "updated_by": frappe.session.user})
    doc.save(ignore_permissions=True) if name else doc.insert(ignore_permissions=True)
    return doc.name
