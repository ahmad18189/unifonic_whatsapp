app_name = "unifonic_whatsapp"
app_title = "Unifonic WhatsApp"
app_publisher = "Integration Team"
app_description = "Two-way WhatsApp via Unifonic for Frappe v15"
app_email = ""
app_license = "MIT"
required_apps = ["frappe"]

before_install = "unifonic_whatsapp.install.after_install"
after_install = "unifonic_whatsapp.install.after_install"
after_migrate = "unifonic_whatsapp.install.after_install"

scheduler_events = {
    "all": ["unifonic_whatsapp.jobs.recover_events"],
    "hourly": ["unifonic_whatsapp.jobs.reconcile_unknown", "unifonic_whatsapp.jobs.replay_unmatched"],
    "daily": ["unifonic_whatsapp.jobs.purge_old_events"],
}

permission_query_conditions = {
    "UW Conversation": "unifonic_whatsapp.services.access.conversation_query",
    "UW Message": "unifonic_whatsapp.services.access.message_query",
}
has_permission = {
    "UW Conversation": "unifonic_whatsapp.services.access.conversation_permission",
    "UW Message": "unifonic_whatsapp.services.access.message_permission",
}
website_route_rules = [{"from_route": "/unifonic-inbox/<path:app_path>", "to_route": "unifonic-inbox"}]

doc_events = {
    "Sales Invoice": {"on_submit": "unifonic_whatsapp.integrations.erpnext.on_submit", "on_cancel": "unifonic_whatsapp.integrations.erpnext.on_cancel"},
    "Sales Order": {"on_submit": "unifonic_whatsapp.integrations.erpnext.on_submit", "on_cancel": "unifonic_whatsapp.integrations.erpnext.on_cancel"},
    "Delivery Note": {"on_submit": "unifonic_whatsapp.integrations.erpnext.on_submit", "on_cancel": "unifonic_whatsapp.integrations.erpnext.on_cancel"},
    "Payment Entry": {"on_submit": "unifonic_whatsapp.integrations.erpnext.on_submit", "on_cancel": "unifonic_whatsapp.integrations.erpnext.on_cancel"},
}
