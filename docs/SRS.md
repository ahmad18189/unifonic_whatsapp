# Software Requirements Specification (SRS)
**Project:** Unifonic WhatsApp Integration | **App:** `unifonic_whatsapp` | **Target:** Frappe Framework v15 | **Version:** 1.0 | **Date:** 2026-10-29

## 1. Purpose and scope
Deliver a standalone installable Frappe v15 app for two-way WhatsApp communication using the Unifonic Conversations API, an agent inbox built with Vue 3 / Frappe UI, approved outbound templates, delivery traceability, and optional notifications from native ERPNext documents. Built to support one or more legal entities and Unifonic applications with strict separation by account.

**Personas:** System Administrator (credentials/deployment), Unifonic Manager (channels, agents, templates, consent, auditing), Agent (assigned/unassigned conversations and replies), ERP Administrator (configures rules), Customer (WhatsApp sender/recipient), Compliance Auditor (evidence access via manager-authorized Frappe role).

**Out of scope in MVP:** Unifonic Campaign API, bulk campaigns, chatbots/AI, formal SLA routing engine, outbound media upload, Meta template submission/create API, CRM replacement, auto-payment capture, native ERPNext accounting reimplementation, number scraping, mass unsolicited sending, end-user WhatsApp authentication/OTP.

## 2. Functional requirements

| ID | Priority | Requirement | Acceptance |
|---|---|---|---|
| FR-001 | P0 | Multiple UW Accounts with unique application ID, company association and encrypted password fields | Account-specific events/messages cannot cross channels |
| FR-002 | P0 | No live send until account enabled and live-sending explicitly enabled | Disabled outbound worker writes Dry Run; no HTTP POST |
| FR-003 | P0 | Guest webhook POST authentication via strong per-account secret and application ID | Invalid secret/app ID rejected before DB insert |
| FR-004 | P0 | Persist each accepted webhook event with dedupe hash and process asynchronously | Duplicate event does not create extra inbound messages |
| FR-005 | P0 | Inbound text, option, image, file, audio, video, location, sticker parsed; preserve content metadata | All supported types visible as transcript metadata |
| FR-006 | P0 | One conversation per account + E.164 phone; latest inbound time drives service window | Duplicate contacts cannot merge between accounts |
| FR-007 | P0 | Outbound session text limited to 4,096 characters and active window since last inbound | Block outside 24-hour window |
| FR-008 | P0 | Refresh templates from provider; only APPROVED templates may be selected | Unknown/unapproved template blocked |
| FR-009 | P0 | Record explicit consent evidence (source, evidence, timestamp), enforce opt-out | Business-initiated sends blocked without opted-in record |
| FR-010 | P0 | Durable queue; each outbound message gets stable referenceId | Ambiguous provider outcome -> Unknown; no blind resend |
| FR-011 | P0 | Handle sent/delivered/read/rejected events; ignore status regressions | Read never becomes Sent because events arrive out-of-order |
| FR-012 | P0 | Poll provider status by reference ID for Unknown/Sending/Submitted | Operator can reconcile without duplicate send |
| FR-013 | P0 | Shared agent inbox with conversation list, history, reply, approved template composer | Functional desktop UI served by Frappe |
| FR-014 | P0 | Manager/agent roles and row-level assigned/unassigned access; no secrets in browser | Unauthorized agent cannot read assigned colleague transcript |
| FR-015 | P1 | Manually enabled ERPNext on-submit/on-cancel template notifications | Only configured document event sends; no blocking ERP transaction |
| FR-016 | P1 | Link outbound notifications to source DocType/document | Audit from message to ERPNext document |
| FR-017 | P1 | Manager assignment, resolve/reopen conversations | Assigned user changes take effect on next request |
| FR-018 | P1 | Structured audit/debug logs and retryable event journal | Failed webhooks can be recovered by scheduler |
| FR-019 | P2 | Agent typing notifications, real-time socket updates, dashboard charts | Follow-up, not MVP |
| FR-020 | P2 | Media proxy and malware scans, catalog browsing and interactive messages | Follow-up after security review |

## 3. Data entities
| DocType | Purpose | Key fields / constraints |
|---|---|---|
| UW Account | API credentials, app ID, company, live-send gate | application_id unique, secrets Password |
| UW Conversation | One contact per account | conversation_key unique, assigned_to, last_inbound_at |
| UW Message | Immutable-origin transcript plus mutable status | idempotency_key unique, reference_id unique outbound, provider message ID, direction, content |
| UW Webhook Event | Idempotent event journal | event_key deterministic SHA-256 name, attempts, payload |
| UW Template | Cached Unifonic approved/other templates | account + name + language (lookup composite) |
| UW Consent | Explicit opt-in/out history snapshot | consent_key unique, evidence/source |
| UW Notification Rule | Optional ERPNext document trigger | source_doctype, trigger, phone_field, template, variable fieldnames |

## 4. Workflow requirements
**Inbound:** Unifonic POST webhook -> validate HTTPS token/app ID -> store event -> enqueue after commit -> normalize E.164 -> find/create conversation -> dedupe provider message -> store inbound -> update last_inbound_at -> display to authorized agents.

**Agent reply:** authorize role and conversation -> confirm last customer inbound less than 24 hours -> create queued outbox record -> background worker recheck window and live gate -> mark Sending and commit -> provider POST with stable referenceId -> Submitted/Unknown/Failed -> reconcile delivery webhook/status polling.

**Business template:** check explicit opt-in -> check approved synced template language and account -> create conversation if manager/system rule -> enqueue -> provider POST -> track statuses.

**ERP event:** native document submit/cancel -> evaluate only enabled UW Notification Rules (including matching company) -> phone from explicitly configured source field -> parameter fields resolved by fieldname only (no dynamic Jinja) -> opt-in and template check -> queue after transaction commit. Never block submit if notification fails; report error to log.

## 5. Nonfunctional requirements
- NFR-001: Frappe Framework 15. No ERPNext mandatory install dependency, but supports ERPNext 15 when present.
- NFR-002: Server secrets encrypted in Frappe Password fields, no frontend exposure or credentials in logs.
- NFR-003: Webhook payload <=256 KB, HTTPS-only at ingress/proxy, log redaction for URL token.
- NFR-004: Store PII with role/access controls; retention 30d for successfully processed raw webhooks (configurable policy required for commercial deployment).
- NFR-005: Idempotent ingestion and stable outbound reference ID. Exactly-once provider delivery is NOT guaranteed by the current published documentation.
- NFR-006: Report malformed webhooks with 4xx errors; persist accepted events; failed processing retry max 8 times, then manual review.
- NFR-007: Index/fetch bounded by 50 conversations and 100 transcript messages per API call; implement pagination/infinite scroll before large production use.
- NFR-008: Safe Arabic UTF-8 text; improve formal RTL layout and Arabic localization before Saudi production rollout.
- NFR-009: Prevent duplicate sends on concurrent workers; product-level proof via concurrency test prior to go-live.
- NFR-010: Frontend requires Node >=20.19; TLS certificate validated by provider API client, redirects refused.

## 6. Dependencies / constraints
Frappe 15 bench with MariaDB, Redis/RQ scheduler/workers and HTTPS reverse proxy; Node >=20.19 frontend build; Unifonic WhatsApp application with PublicId, Secret, Application ID and enabled inbound/status webhooks; approved WhatsApp templates and documented end-user opt-in. Follow provider limits and Meta policy.

## 7. Sign-off and open decisions
- Confirm actual Unifonic send API success envelopes and errors in sandbox (docs focus primarily on request examples).
- Confirm whether Unifonic signs callbacks; if so replace URL token or add signature check. Token-in-query must be excluded from proxy logs.
- Decide retention/legal DPA requirements (Türkiye/KSA depending company).
- Decide agent visibility model: current default allows all agents to view unassigned chats; manager assigns for private handling.
- Confirm how customer phone numbers are stored in each ERPNext DocType; rules require exact E.164 field.
- Confirm whether template messages from ERPNext should be sent for submit, cancel, or only customer-approved transactional events.
- Confirm whether more than one Unifonic application/account is deployed on the site.

## 8. Traceability
FR-003/004 -> api/webhook.py + services/events.py; FR-007/008/009 -> services/sending.py, templates.py, consent.py; FR-010/011/012 -> client.py, sending.py, events.py, jobs.py; FR-013/014 -> api/inbox.py, frontend/src/Inbox.vue, services/access.py; FR-015/016 -> integrations/erpnext.py.
