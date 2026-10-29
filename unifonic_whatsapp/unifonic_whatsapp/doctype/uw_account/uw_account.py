import frappe
from frappe.model.document import Document


class UWAccount(Document):
    def _secret(self, fieldname):
        # On first insert a Password field may not yet be present in __Auth;
        # on update a masked value is shown to the form.
        submitted = self.get(fieldname)
        if submitted and str(submitted).strip('*'):
            return str(submitted)
        if self.is_new():
            return ""
        return self.get_password(fieldname) or ""

    def validate(self):
        self.api_base_url = "https://apis.unifonic.com/v1"
        if self.enabled and not self._secret("api_secret"):
            frappe.throw("Secret is required to enable account")
        if self.enabled and len(self._secret("webhook_token")) < 32:
            frappe.throw("Webhook token must contain at least 32 characters")
        if self.live_sending_enabled and not self.enabled:
            frappe.throw("Enable account first")
        if self.company and frappe.db.exists("DocType", "Company") and not frappe.db.exists("Company", self.company):
            frappe.throw("Unknown ERPNext Company")
