"""Recovery and reconciliation; safe to run repeatedly."""
import frappe
from frappe.utils import add_days, now_datetime
from unifonic_whatsapp.services.events import process
from unifonic_whatsapp.services.client import UnifonicClient, UnifonicError


def recover_events():
    for name in frappe.get_all("UW Webhook Event", filters={"status": ["in", ["Received", "Failed"]],
                                                              "attempts": ["<", 8]},
                               pluck="name", limit_page_length=100, order_by="creation asc"):
        frappe.enqueue("unifonic_whatsapp.services.events.process", event_name=name, queue="short")


def replay_unmatched():
    for name in frappe.get_all("UW Webhook Event", filters={"status": "Pending Match",
                                                              "attempts": ["<", 8]},
                               pluck="name", limit_page_length=100, order_by="creation asc"):
        frappe.enqueue("unifonic_whatsapp.services.events.process", event_name=name, queue="short")


def reconcile_unknown():
    messages = frappe.get_all("UW Message", filters={"status": ["in", ["Unknown", "Submitted", "Sending"]],
                                                    "direction": "Outbound"},
                              fields=["name", "account", "reference_id", "external_message_id", "status"],
                              limit_page_length=100, order_by="creation asc")
    for msg in messages:
        try:
            client = UnifonicClient(msg.account)
            if msg.reference_id:
                entries = client.status_by_reference(msg.reference_id)
            elif msg.external_message_id:
                entries = client.status_by_message(msg.external_message_id)
            else:
                continue
            if isinstance(entries, dict):
                entries = entries.get("data") or entries.get("messages") or []
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                mapped = {"QUEUED": "Submitted", "SENT": "Sent", "DELIVERED": "Delivered",
                          "READ": "Read", "REJECTED": "Failed", "FAILED": "Failed"}.get(
                              str(entry.get("status") or "").upper())
                if not mapped:
                    continue
                # Avoid stale poll results overriding webhook-delivered state.
                current = frappe.db.get_value("UW Message", msg.name, "status")
                ranks = {"Unknown": -1, "Sending": -1, "Submitted": 0, "Sent": 1,
                         "Delivered": 2, "Read": 3, "Failed": 4}
                if current in ("Read", "Delivered") and mapped == "Failed":
                    continue
                if current not in ("Failed",) and (current not in ranks or ranks[mapped] >= ranks[current]):
                    update = {"status": mapped}
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
    for name in frappe.get_all("UW Webhook Event", filters={"status": "Processed", "received_at": ["<", cutoff]},
                               pluck="name", limit_page_length=500):
        frappe.delete_doc("UW Webhook Event", name, ignore_permissions=True, force=True)
