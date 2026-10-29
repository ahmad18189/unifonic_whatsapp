import frappe
from frappe.model.document import Document
from unifonic_whatsapp.services.phone import normalize_phone

class UWConsent(Document):
    def validate(self):
        self.contact = normalize_phone(self.contact)
        self.consent_key = f"{self.account}|{self.contact}"
        if self.status == "Opted In" and (not self.source or not self.evidence):
            frappe.throw("Explicit opt-in evidence is required")
