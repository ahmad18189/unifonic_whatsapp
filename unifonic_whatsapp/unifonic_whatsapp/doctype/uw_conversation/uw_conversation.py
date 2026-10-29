from frappe.model.document import Document
from unifonic_whatsapp.services.phone import normalize_phone

class UWConversation(Document):
    def validate(self):
        self.contact = normalize_phone(self.contact)
        self.conversation_key = f"{self.account}|{self.contact}"
