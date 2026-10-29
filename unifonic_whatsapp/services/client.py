"""Server-only Unifonic Conversations API client. Never expose API credentials to the browser."""
import requests
from urllib.parse import urljoin
import frappe

BASE = "https://apis.unifonic.com/v1/"


class UnifonicError(Exception):
    def __init__(self, message, status_code=None, uncertain=False):
        super().__init__(message)
        self.status_code = status_code
        self.uncertain = uncertain


class UnifonicClient:
    def __init__(self, account):
        if isinstance(account, str):
            account = frappe.get_doc("UW Account", account)
        if not account.enabled:
            raise UnifonicError("Account disabled")
        self.account = account
        self.session = requests.Session()
        self.session.headers.update({
            "PublicId": account.public_id,
            "Secret": account.get_password("api_secret"),
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def request(self, method, path, *, payload=None, params=None):
        if not path.startswith("/"):
            path = "/" + path
        try:
            res = self.session.request(method, urljoin(BASE, path.lstrip("/")),
                                       json=payload, params=params, timeout=(5, 20),
                                       allow_redirects=False)
        except requests.RequestException as exc:
            # Timeout / network failure: provider may have accepted the message.
            raise UnifonicError("Network error; delivery is uncertain", uncertain=True) from exc
        if not (200 <= res.status_code < 300):
            uncertain = res.status_code >= 500 or res.status_code in (408, 409, 425, 429)
            raise UnifonicError(f"Unifonic HTTP {res.status_code}", res.status_code, uncertain)
        try:
            return res.json()
        except ValueError:
            raise UnifonicError("Provider returned non-JSON response", uncertain=(method == "POST"))

    def send(self, phone, content, reference_id):
        return self.request("POST", "/messages", payload={
            "recipient": {"contact": phone, "channel": "whatsapp"},
            "content": content,
            "referenceId": reference_id,
        })

    def templates(self):
        return self.request("GET", "/whatsapp/message_templates")

    def status_by_reference(self, reference_id):
        return self.request("GET", "/messages/status_by_ref_id", params={"referenceIds": reference_id})

    def status_by_message(self, message_id):
        return self.request("GET", "/messages/status", params={"messageIds": message_id})


def extract_message_id(response):
    """Response envelope differs across integrations; never assume a missing ID means failure."""
    if isinstance(response, list):
        for child in response:
            found = extract_message_id(child)
            if found:
                return found
    if isinstance(response, dict):
        for key in ("messageId", "message_id"):
            if response.get(key):
                return str(response[key])
        for key in ("data", "message", "messages", "result"):
            if key in response:
                found = extract_message_id(response[key])
                if found:
                    return found
    return None
