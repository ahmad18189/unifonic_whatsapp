# Release gate — production go-live signoff

- [ ] Frappe 15 exact version recorded, ERPNext optional app version recorded.
- [ ] Bench install, migrate and frontend build succeed; production route tested.
- [ ] Unifonic credentials and applicationId confirmed; no secrets in Git, logs or UI.
- [ ] Signed webhook callback support checked with Unifonic; token fallback risk accepted or mitigated.
- [ ] Query string completely redacted in logs/APM; HTTPS TLS enforced.
- [ ] Webhook dedupe, event recovery, and out-of-order tests passed.
- [ ] Concurrent worker dispatch proven safe with multiple workers.
- [ ] Provider sandbox POST and exact response schema verified with sanitized samples.
- [ ] Unifonic sandbox inbound text, approved template, delivered/read tests passed.
- [ ] Opt-in wording + evidence retention approved by company legal/compliance.
- [ ] 24h service window and opt-out enforcement tested.
- [ ] Manager/agent cross-account and assignment permissions pen-tested.
- [ ] ERPNext rule mapped to real phone field and company, no ledger side effects.
- [ ] Data retention requirements, incident contact, breach response and DPA approved.
- [ ] Backups, restore, rollback and monitoring tested.
- [ ] Production sending toggle enabled only after signoff.

**Release approver:** _____________________  **Date:** __________
