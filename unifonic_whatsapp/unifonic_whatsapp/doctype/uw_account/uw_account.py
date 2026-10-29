from urllib.parse import urlsplit

import frappe
from frappe.model.document import Document
from unifonic_whatsapp.services.client import DEFAULT_BASE_URL


def check_base_url(url):
    """Return the normalized base URL or raise ValueError. The secret is sent to this host."""
    url = (url or "").strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("API base URL must be an absolute https:// URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("API base URL must not contain credentials, a query or a fragment")
    return url


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
        try:
            self.api_base_url = check_base_url(self.api_base_url or DEFAULT_BASE_URL)
        except ValueError as exc:
            frappe.throw(str(exc))
        if self.api_base_url != DEFAULT_BASE_URL and (self.is_new() or self.has_value_changed("api_base_url")):
            # The API secret is sent to this host, so only a System Manager may redirect it,
            # and never while messages could be going out live.
            if "System Manager" not in frappe.get_roles():
                frappe.throw("Only a System Manager may change the API base URL")
            if self.live_sending_enabled:
                frappe.throw("Turn off live sending before changing the API base URL")
        if self.enabled and not self._secret("api_secret"):
            frappe.throw("Secret is required to enable account")
        if self.enabled and len(self._secret("webhook_token")) < 32:
            frappe.throw("Webhook token must contain at least 32 characters")
        if self.live_sending_enabled and not self.enabled:
            frappe.throw("Enable account first")
        if self.company and frappe.db.exists("DocType", "Company") and not frappe.db.exists("Company", self.company):
            frappe.throw("Unknown ERPNext Company")
