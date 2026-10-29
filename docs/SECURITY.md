# Security and privacy model

## Secret handling
- Unifonic `PublicId`, API `Secret`, `Webhook Token` belong to **UW Account**. The two secrets use Frappe `Password` fields, never site config text, JavaScript, Git or log bodies.
- Treat webhook token as a bearer credential. Generate at least 32 random characters (prefer `secrets.token_urlsafe(48)`). Rotate when compromised.
- The current official documentation describes configuration of a webhook URL but does not define a signed callback mechanism. This implementation uses a token URL query parameter plus strict application ID checks. **This is not proof the request originated from Unifonic.**
- Require HTTPS. Disable logging of full query strings at Nginx, load balancer, WAF, tracing and APM for `/api/method/unifonic_whatsapp.api.webhook.receive`. Do not include token in errors or support tickets.
- Where supported, restrict ingress network source IPs only after Unifonic provides authoritative egress IP ranges. Do not invent provider CIDRs.

## Access-control matrix
| Function | System Manager | Unifonic Manager | Unifonic Agent | Guest |
|---|---|---|---|---|
| Configure API account | Yes | Yes | No | No |
| Manage consent | Yes | Yes | No | No |
| Sync templates | Yes | Yes | No | No |
| View template metadata | Yes | Yes | Yes | No |
| View conversations | All | All | Unassigned and own | No |
| View message payloads | All | All | Unassigned and own | No |
| Send within open conversation | Yes | Yes | Unassigned and own | No |
| Initiate new conversation via template | Yes | Yes | No | No |
| Assign any conversation | Yes | Yes | No | No |
| Webhook POST | Token authenticated | Token authenticated | Token authenticated | Token authenticated |
| View raw webhook journal | Yes | Yes | No | No |

**Note:** Frappe System Manager can access all data; use normal Frappe role governance and audit trail. Agent assignments are enforced in API authorization and DocType query/has_permission hooks.

## Consent / WhatsApp policy
- Record consent with source, evidence, exact E.164 number, account, operator, timestamp; status `Opted In` is required for business-initiated approved templates.
- Receiving a message allows reply within last inbound 24-hour service window, **not blanket permission for recurring marketing templates**.
- Opt-out must be written immediately. The worker rechecks consent just before POST.
- Do not use contact scraping or unapproved bulk broadcasts. Retain opt-in evidence per applicable law.

## Data storage and privacy
- UW Webhook Event stores original payload (phone numbers, names, possibly media URLs). It is manager-only and processed events are purged after 30 days by the included scheduler. Failed events require manual remediation and retention policy.
- UW Message retains transcript data until manually deleted; create business-approved retention/purge and data-subject process before production.
- The current client displays plain text; Vue escapes content in interpolation. Never use `v-html` for customer messages.
- Media URLs are not fetched, proxied or exposed as clickable links in the MVP. Before implementing: allowlist hosts after verified provider contract, SSRF guard, size caps, MIME sniffing, malware scanning, private File storage and expiry.
- Enforce company-scoped data permissions for future ERPNext Customer/Contact linking; do not assume a shared phone belongs to only one customer.

## Known gaps before production
1. No provider signature specification available from supplied docs; obtain confirmation/upgrade to cryptographically verifiable webhook authentication.
2. No validated live Unifonic rate limits or API response schema; sandbox test required.
3. The provider's reference ID is only a reconciliation key, not documented as an exactly-once idempotency guarantee.
4. Existing agent access model exposes all **unassigned** chats to agents; obtain customer sign-off.
5. No configurable raw transcript retention, DLP, antivirus scanning, SIEM alerts or legal DPA yet.
6. Live frontend requires a tested CSP and CSRF session configuration for the deployment environment.
