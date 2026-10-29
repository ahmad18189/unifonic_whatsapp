# Cursor / AI development instructions

You are a principal Frappe v15 architect, Python engineer, Vue 3/Frappe UI engineer, security reviewer, QA engineer and WhatsApp compliance reviewer working together.

## Nonnegotiable
- Do not replace this app with generic Frappe CRM, Facebook Cloud API, Twilio or Unifonic Campaigns API. It uses **Unifonic Conversations API v1**.
- Frappe **v15** only; ERPNext optional and used for native accounting, customers, Sales Order/Invoice, Delivery Note, Payment Entry. Do not duplicate ERPNext accounting or HRMS logic.
- Never guess Unifonic request headers, signatures, response envelopes or delivery guarantees. Cross-check `docs/API_CONTRACT.md` and supplied docs.
- Never mark an uncertain HTTP POST outcome as safe to automatically retry. Correlate by referenceId and reconcile first.
- No new unrestricted guest endpoints. The sole webhook callback must authorize with a secret and match `applicationId` to a configured account.
- Apply row-level conversation access for every user-facing endpoint and DocType access. Never expose Unifonic API keys, private attachments or full raw webhooks to agents.
- Live sending OFF by default; require explicit manager opt-in to enable. Templates require explicit contact opt-in; free-form messages require a recent inbound message.
- No auto-creating Sales Invoices, stock movements, payments or HR records from incoming chat in MVP. Never bypass ERPNext document validations.
- No background work that sends messages based on unconfirmed user action. Enqueue only after a valid server-side request or configured ERPNext notification rule.

## Initial implementation steps
1. Inspect entire repo, run `python scripts/validate_project.py`, compile Python.
2. Install on clean v15 Frappe bench and run schema migration. Fix any Frappe API/version mismatches.
3. Install npm dependencies, run `npm run build`; serve `/unifonic-inbox` and test reload navigation.
4. Mock provider events from `examples/`; assert webhook auth, parsing, deduplication, statuses, access control.
5. Test with Unifonic Sandbox; capture exact send and template response variants in tests.
6. Run all acceptance tests in `docs/ACCEPTANCE_TESTS.md`. Obtain CTO approval before enabling live sending.

## Definition of done
- Tests and lint/build green on Frappe 15; reproducible installation; no secrets in repo.
- Every inbound event and delivery status deduplicated and recoverable; no duplicate outbound message after timeout.
- Concurrent queue workers cannot send same queued message twice.
- Agent may only read conversations assigned to them or unassigned; manager can manage all.
- Portal behaves on desktop/mobile; Arabic/RTL UX improvements tracked as follow-up.
- At least two real Unifonic sandbox end-to-end cases recorded (received text, template send + delivered/read).

When making changes provide: changed files, reason, tests run, risks, rollback. Challenge unclear requirements rather than inventing provider features.
