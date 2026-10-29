# Test evidence

## 2026-10-29 — local Frappe v15 dev bench (no Unifonic traffic)

**Environment:** `dev/docker-compose.yml` on macOS (Apple Silicon): Frappe 15.125.0, Python 3.12.16, MariaDB 10.6, Redis 7, site `uw.localhost`. Provider HTTP mocked in tests; HTTP checks used a dev account with live sending OFF.

**Suite:** `bench --site uw.localhost run-tests --app unifonic_whatsapp` → `Ran 41 tests … OK`, three consecutive runs.

| Case | Result | How |
|---|---|---|
| AT-01 install + migrate | Pass | `install-app`, `migrate`: 7 DocTypes, roles Unifonic Agent/Manager, `UW Message.last_reconciled_at` column present |
| AT-02 route auth | Pass | HTTP: guest → 301 `/login?redirect-to=/unifonic-inbox`; agent role → 200; logged-in user without role → 403 (page and API) |
| AT-03 bad/missing token | Pass | Test + HTTP: no token, wrong token, unknown account → 403, no event stored |
| AT-04 other `applicationId` | Pass | Test + HTTP → 403, no event stored |
| AT-05 replay | Pass | Test + HTTP: same event POSTed twice → 1 UW Webhook Event, 1 deduplicated RQ job, 1 inbound message |
| AT-06 / AT-07 conversation keying | Pass | Tests |
| AT-09 row access | Pass | Test: other agent denied messages + list; assignee and manager allowed |
| AT-10 reply in window | Pass | Test + UI: reply sent from `/unifonic-inbox` → Queued → worker → Dry Run, `attempt_count` 0, no POST |
| AT-11 reply after 24h | Pass | Test |
| AT-12 / AT-13 / AT-14 template gates | Pass | Tests |
| AT-15 / AT-16 status ordering | Pass | Tests via webhook path |
| AT-18 double dispatch | Pass (single connection) | Test: second dispatch makes no POST; claim `UPDATE` rowcount 1 then 0. Two-process race not yet run |
| AT-19 timeout | Pass | Test: Unknown, not retried |
| AT-21 401 | Pass | Test: Failed, secret not in error |
| AT-27 purge | Pass | Test: processed deleted, failed kept |
| AT-28 nested route + assets | Pass | HTTP: nested route 200 with boot data incl. `csrf_token`; assets 200; UI loads with no console errors |
| AT-29 opt-out before dispatch | Pass | Test: Failed "Consent withdrawn", no POST |
| CSRF on inbox POST | Pass | HTTP: without token 400, with page token 200 |

**Not covered here:** AT-08 (media/location payloads), AT-17, AT-20, AT-22–AT-25 (need ERPNext), AT-26, AT-30 (reverse proxy), and all Unifonic sandbox cases.

**Findings during this run:**
- Fixed: the page module was named `unifonic-inbox.py`; Frappe loads `unifonic_inbox.py`, so `get_context` never ran (no guest redirect, no role check, no CSRF token in the page).
- Observed: the dev server access log records the full webhook URL including `token=`. Production proxies/APM must redact the query string (SECURITY.md, AT-30), or the token should move to a header if Unifonic supports one.
- Event jobs run as user `Guest` (enqueued from the guest webhook). Writes use `ignore_permissions`, so this works, but records are owned by Guest.
