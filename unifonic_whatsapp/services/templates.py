import json
import frappe
from frappe.utils import now_datetime
from unifonic_whatsapp.services.client import UnifonicClient


def sync_templates(account):
    """Fetch approved + nonapproved metadata. No writes to Unifonic templates."""
    raw = UnifonicClient(account).templates()
    if isinstance(raw, dict):
        raw = raw.get("data") or raw.get("templates") or []
    if not isinstance(raw, list):
        raise ValueError("Unifonic template list response not recognized")
    count = 0
    for obj in raw:
        if not isinstance(obj, dict) or not obj.get("name") or not obj.get("language"):
            continue
        filters = {"account": account, "template_name": obj["name"],
                   "language": obj["language"]}
        existing = frappe.db.get_value("UW Template", filters, "name")
        doc = frappe.get_doc("UW Template", existing) if existing else frappe.new_doc("UW Template")
        doc.update({**filters, "category": obj.get("category"),
                    "status": obj.get("status", "UNKNOWN"),
                    "provider_template_id": str(obj.get("id") or ""),
                    "components_json": json.dumps(obj.get("components") or [], ensure_ascii=False),
                    "last_synced_at": now_datetime()})
        doc.save(ignore_permissions=True) if existing else doc.insert(ignore_permissions=True)
        count += 1
    return count
