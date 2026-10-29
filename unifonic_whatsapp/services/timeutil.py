from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import frappe
from frappe.utils import now_datetime


def provider_time(raw):
    """Convert RFC3339 from Unifonic to the site's naive local datetime format."""
    if not raw:
        return now_datetime()
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt
        tz = ZoneInfo(frappe.utils.get_system_timezone())
        return dt.astimezone(tz).replace(tzinfo=None)
    except (ValueError, TypeError):
        return now_datetime()
