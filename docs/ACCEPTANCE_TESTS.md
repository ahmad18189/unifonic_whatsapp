# Acceptance test matrix — Frappe v15 + Unifonic sandbox

| Case | Steps | Expected |
|---|---|---|
| AT-01 | Install on new Frappe 15 bench | All seven DocTypes and two roles exist; no ERPNext required |
| AT-02 | Build frontend and open `/unifonic-inbox` | Authenticated page loads, guest redirected |
| AT-03 | POST webhook with no/invalid token | 403 / PermissionError, no journal record |
| AT-04 | POST with valid token but another `applicationId` | Rejected, no journal record |
| AT-05 | POST examples/webhook_inbound.json twice | One UW Webhook Event and one inbound UW Message |
| AT-06 | POST two different events from same account/phone | Exactly one UW Conversation, two message rows |
| AT-07 | POST event from different account with same phone | Two separate conversations |
| AT-08 | Media/option/location event replay | Content metadata preserved, UI plain text no injection |
| AT-09 | Agent A assigned to chat; Agent B accesses message API | Agent B denied; Manager allowed |
| AT-10 | Agent replies after inbound <24h | Queued, Dry Run in staging; no external HTTP |
| AT-11 | Agent replies at >=24h | Blocked before enqueue and before worker POST |
| AT-12 | Template without Opted In UW Consent | Blocked |
| AT-13 | Template not APPROVED / mismatched language | Blocked |
| AT-14 | Template with consent + approved metadata | Queued; referenceId unique and persisted |
| AT-15 | Callback message.delivered then message.sent | Status stays Delivered |
| AT-16 | Callback message.read then message.rejected | Status stays Read |
| AT-17 | Delivery webhook before provider POST response | Post-response processing never downgrades delivery |
| AT-18 | Worker A and Worker B claim same Queued record | Exactly one outgoing provider POST |
| AT-19 | Outbound POST timeout / 5xx | Mark Unknown, no automatic retry; status by referenceId attempted |
| AT-20 | Worker crash after Sending commit | Do not requeue on restart; reconcile |
| AT-21 | Outbound HTTP 401/400 | Failed with safe status, no credential leaks |
| AT-22 | ERPNext Sales Invoice submit with disabled rule | Zero outbox messages |
| AT-23 | ERPNext Sales Invoice submit with enabled rule but no opt-in | Zero outbox messages and native submit completes |
| AT-24 | ERPNext Sales Invoice submit with enabled rule, proper template and consent | One linked outbox; no accounting mutation |
| AT-25 | Account company differs from source invoice company | No outbox created |
| AT-26 | Frappe scheduler recovers 1 Failed webhook | Eventually Processed (up to max attempts) |
| AT-27 | Purge daily: Processed webhook older 30d | Deleted, unprocessed events retained |
| AT-28 | Build/reload Vue on nested route | 200 HTML + valid static assets |
| AT-29 | User opt-out occurs between queue and worker dispatch | Worker blocks send |
| AT-30 | Confirm reverse-proxy access logs | No webhook token present |

**Status of these tests in this ZIP:** the Python code and JSON structure have been statically validated. The Frappe integration tests and live/sandbox Unifonic cases above **must be executed** on your staging bench. Do not record these tests as passed without evidence.
