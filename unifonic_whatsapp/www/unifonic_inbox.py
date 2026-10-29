import frappe
from unifonic_whatsapp.services.access import is_agent
no_cache = 1

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=%2Funifonic-inbox"
        raise frappe.Redirect
    if not is_agent():
        raise frappe.PermissionError("Unifonic agent role required")
    # Injected onto window by frappe-ui's jinjaBootData; frappeRequest reads window.csrf_token.
    context.boot = {"csrf_token": frappe.sessions.get_csrf_token(), "user": frappe.session.user}
