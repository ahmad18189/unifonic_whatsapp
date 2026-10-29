import frappe

MANAGERS = {"System Manager", "Unifonic Manager"}


def is_manager(user=None):
    return bool(MANAGERS.intersection(frappe.get_roles(user or frappe.session.user)))


def is_agent(user=None):
    return is_manager(user) or "Unifonic Agent" in frappe.get_roles(user or frappe.session.user)


def require_agent():
    if frappe.session.user == "Guest" or not is_agent():
        frappe.throw("Unifonic agent role required", frappe.PermissionError)


def require_manager():
    if frappe.session.user == "Guest" or not is_manager():
        frappe.throw("Unifonic manager role required", frappe.PermissionError)


def can_access_conversation(conversation, user=None):
    user = user or frappe.session.user
    return (user != "Guest" and (is_manager(user) or
           ("Unifonic Agent" in frappe.get_roles(user) and
            (not conversation.assigned_to or conversation.assigned_to == user))))


def require_conversation(name):
    require_agent()
    conversation = frappe.get_doc("UW Conversation", name)
    if not can_access_conversation(conversation):
        frappe.throw("Conversation access denied", frappe.PermissionError)
    return conversation


def conversation_query(user=None):
    user = user or frappe.session.user
    if is_manager(user):
        return None
    if user == "Guest" or not is_agent(user):
        return "1=0"
    escaped = frappe.db.escape(user)
    return f"(IFNULL(`tabUW Conversation`.`assigned_to`, '') = '' OR `tabUW Conversation`.`assigned_to` = {escaped})"


def message_query(user=None):
    user = user or frappe.session.user
    if is_manager(user):
        return None
    if user == "Guest" or not is_agent(user):
        return "1=0"
    escaped = frappe.db.escape(user)
    return ("EXISTS (SELECT 1 FROM `tabUW Conversation` c WHERE c.name = "
            "`tabUW Message`.`conversation` AND "
            f"(IFNULL(c.assigned_to, '') = '' OR c.assigned_to = {escaped}))")


def conversation_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if permission_type in ("write", "create", "delete", "submit", "cancel"):
        return is_manager(user)
    return can_access_conversation(doc, user)


def message_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if permission_type in ("write", "create", "delete", "submit", "cancel"):
        return is_manager(user)
    conversation = frappe.get_doc("UW Conversation", doc.conversation)
    return can_access_conversation(conversation, user)
