# Cursor build plan (milestones and acceptance gates)

**M0 Foundation / staging:** create clean Frappe v15 site with worker + scheduler; install app; confirm seven DocTypes exist and roles are created; no regressions to ERPNext accounting. Fix schema/version deviations in the repo (not local production patches). Output screenshot of `/app/uw-account` and successful migration log.

**M1 Provider adapter (P0):** compare code request paths, authentication and template schema to live Unifonic docs. Mock all 2xx/4xx/5xx/timeout cases. Verify `referenceId` correlation with Unifonic Sandbox. Production default OFF. Add a `test_connection` server-side manager-only method **only after** confirming a safe read endpoint.

**M2 Webhooks (P0):** configure secret callback; test event persistence and replay, duplicate `eventId`, duplicate `messageId`, mismatched `applicationId`, malformed JSON, oversized payload, text/option/media/location events. Run concurrent requests; assert one stored inbound message and one conversation.

**M3 Outbound (P0):** queued session messages only when inbound within 24h, approved template sends only with opt-in. Test no resend on unknown HTTP outcome, status reconciling, out-of-order delivery statuses, multiworker claim. Validate provider response envelope.

**M4 Inbox UI (P0):** npm build and route; conversation list; transcript; message status; template picker; assignment/resolve; UX clear about disabled live send. Improve RTL Arabic support and agent access error flows. Browser refresh on nested route works.

**M5 ERPNext hooks (P1):** configure one UW Notification Rule on Sales Invoice in staging; map exact recipient E.164 custom field; confirm approved template and explicit opt-in; verify no duplicate send when submitted once, and no sending on draft edits. Add test that failure in notification does not block ERP document posting.

**M6 Hardening (P1):** review audit retention, role matrix, failed event queue, rate limiting, reverse-proxy secret masking, security tests and privacy impact assessment; record rollback, alerting and SLOs. Performance test 1,000 inbound webhook events and confirm recoverable backlog.

**M7 Go-live:** rotate sandbox keys into production credentials via UW Account, retain live sending disabled until explicit sign-off; switch callback URLs, send 1 opted-in template; verify delivered and read; enable production notifications selectively.

## Client audit personas (challenge assumptions)
- **Operations Manager:** Does every team agent see unassigned conversations? Who owns reassignment and SLA?
- **Sales:** Does customer number accurately link to Customer or Lead, or could two customers share a number?
- **Compliance:** Where was opted-in consent recorded? Does opt-out block templates immediately? Can audits reconstruct send authorizations?
- **CTO:** Will a worker restart duplicate a provider POST? Can two tenant apps see each other's traffic? Are secrets logged?
- **Finance:** Can automation send customer a wrong company invoice, or fail without interrupting accounting?
- **QA:** Can inbound message be repeated or delayed? What happens if webhook status arrives before POST response?

## Cursor starter prompt
Implement and verify the existing `unifonic_whatsapp` Frappe v15 project. Read `AGENTS.md` and all `docs/*.md` first. Do not rewrite ERPNext accounting. Start by installing on a staging Frappe v15 bench and building the Vue frontend. Run tests, identify version-specific failures, patch the source, and provide test evidence and changed-file summaries. Treat live Unifonic integration behavior as unverified until sandbox tests succeed. Never enable live sending as part of tests without explicit permission.
