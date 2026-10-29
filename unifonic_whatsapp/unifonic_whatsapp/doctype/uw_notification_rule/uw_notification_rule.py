import json
import frappe
from frappe.model.document import Document

class UWNotificationRule(Document):
    def validate(self):
        if not frappe.db.exists("DocType", self.source_doctype):
            frappe.throw("Unknown source DocType")
        meta = frappe.get_meta(self.source_doctype)
        if not meta.has_field(self.phone_field):
            frappe.throw("Phone field must exist on source DocType")
        names = json.loads(self.parameter_fields_json or "[]")
        if not isinstance(names, list) or len(names) > 30:
            frappe.throw("Body parameter fieldnames must be a JSON array <= 30")
        for name in names:
            if not isinstance(name, str) or not meta.has_field(name):
                frappe.throw("Unknown body parameter field")
        template = frappe.get_doc("UW Template", self.template)
        if template.account != self.account:
            frappe.throw("Template belongs to a different account")
