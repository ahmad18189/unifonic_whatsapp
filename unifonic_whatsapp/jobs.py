"""Recovery and reconciliation; safe to run repeatedly."""
import frappe
from frappe.utils import add_days, now_datetime
from unifonic_whatsapp.services.events import enqueue_process
from unifonic_whatsapp.services.client import UnifonicClient, UnifonicError

# Submitted messages normally settle via webhook; stop polling them after this age.
SUBMITTED_POLL_DAYS = 7
POLL_STATUS = {"QUEUED": "Submitted", "SENT": "Sent", "DELIVERED": "Delivered",
               "READ": "Read", "REJECTED": "Failed", "FAILED": "Failed"}
POLL_RANK = {"Unknown": -1, "Sending": -1, "Submitted": 0, "Sent": 1,
             "Delivered": 2, "Read": 3, "Failed": 4}


def recover_events():
    for name in frappe.get_all("UW Webhook Event", filters={"status": ["in", ["Received", "Failed"]],
                                                              "attempts": ["<", 8]},
                               pluck="name", limit_page_length=100, order_by="creation asc"):
        enqueue_process(name)


def replay_unmatched():
    for name in frappe.get_all("UW Webhook Event", filters={"status": "Pending Match",
                                                              "attempts": ["<", 8]},
                               pluck="name", limit_page_length=100, order_by="creation asc"):
        enqueue_process(name)


def poll_target(current, mapped):
    """Status to store for a polled result, or None to keep the current one."""
    if current == "Failed" or (current in ("Read", "Delivered") and mapped == "Failed"):
        return None
    if current in POLL_RANK and POLL_RANK[mapped] < POLL_RANK[current]:
        return None
    return mapped


def reconcile_unknown():
    # Least-recently-polled first, so a backlog of messages that never settle cannot
    # starve newer ones. Unknown/Sending stay eligible until an operator resolves them.
    messages = frappe.get_all("UW Message",
                              filters={"status": ["in", ["Unknown", "Submitted", "Sending"]],
                                       "direction": "Outbound"},
                              or_filters={"status": ["in", ["Unknown", "Sending"]],
                                          "creation": [">", add_days(now_datetime(), -SUBMITTED_POLL_DAYS)]},
                              fields=["name", "account", "reference_id", "external_message_id", "status"],
                              limit_page_length=100, order_by="last_reconciled_at asc, creation asc")
    for msg in messages:
        if not (msg.reference_id or msg.external_message_id):
            continue
        frappe.db.set_value("UW Message", msg.name, "last_reconciled_at", now_datetime(),
                            update_modified=False)
        try:
            client = UnifonicClient(msg.account)
            if msg.reference_id:
                entries = client.status_by_reference(msg.reference_id)
            else:
                entries = client.status_by_message(msg.external_message_id)
            if isinstance(entries, dict):
                entries = entries.get("data") or entries.get("messages") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                mapped = POLL_STATUS.get(str(entry.get("status") or "").upper())
                if not mapped:
                    continue
                # Avoid stale poll results overriding webhook-delivered state.
                current = frappe.db.get_value("UW Message", msg.name, "status")
                target = poll_target(current, mapped)
                if target:
                    update = {"status": target}
                    if entry.get("messageId"):
                        update["external_message_id"] = entry["messageId"]
                    frappe.db.set_value("UW Message", msg.name, update)
        except (UnifonicError, ValueError):
            continue
        except Exception:
            frappe.log_error(title="Unifonic reconciliation", message=frappe.get_traceback())


def purge_old_events():
    cutoff = add_days(now_datetime(), -30)
    # Delete only processed events; failures need an operator-reviewed retention decision.
    # Bulk delete so the purge keeps up with any daily volume.
    frappe.db.delete("UW Webhook Event", {"status": "Processed", "received_at": ("<", cutoff)})
