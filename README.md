# Unifonic WhatsApp for Frappe 15

**Status:** functional reference implementation / integration candidate. **Not yet production-validated** against a live Unifonic tenant or a Frappe bench. Use a staging site, complete the release checklist, and obtain approval before live traffic.

A standalone custom Frappe application providing:

- Multiple Unifonic WhatsApp applications/accounts, protected server-side credentials.
- Incoming message + delivery status webhooks with token gate, app ID validation, event journal, deduplication, retries and audits.
- Outgoing WhatsApp session text (24-hour inbound window), opt-in gated approved templates.
- Transactional outbound queue; ambiguous remote outcomes are reconciled, never blindly resent.
- Vue 3 + Frappe UI agent inbox at `/unifonic-inbox`.
- Explicit role permissions (Unifonic Manager / Unifonic Agent), assignment and resolve/reopen.
- Manually enabled ERPNext notifications for Sales Invoice, Sales Order, Delivery Note and Payment Entry, using configurable approved templates.
- Template sync, campaign-free by design. **This is the Unifonic Conversations API, not the Campaigns or External Bots API.**

## Install (Frappe Framework v15)

From your existing bench on an isolated site:

```bash
cd ~/frappe-bench
# Copy/unzip this project to apps/unifonic_whatsapp first, OR add it as a Git repo.
./env/bin/pip install -e apps/unifonic_whatsapp
# If copied manually rather than installed with `bench get-app`, register it:
grep -qxF 'unifonic_whatsapp' sites/apps.txt || echo 'unifonic_whatsapp' >> sites/apps.txt
bench --site your-staging.example.com install-app unifonic_whatsapp
bench --site your-staging.example.com migrate
bench build --app unifonic_whatsapp
bench --site your-staging.example.com clear-cache
bench restart
```

To build the frontend, **Node >= 20.19**:

```bash
cd ~/frappe-bench/apps/unifonic_whatsapp/frontend
npm install
npm run build
cd ~/frappe-bench
bench --site your-staging.example.com clear-cache
```

The Vite plugin writes `unifonic_whatsapp/www/unifonic-inbox.html` and frontend assets under `unifonic_whatsapp/public/frontend`. A **frontend build is required** before the inbox route works; generated artifacts are not included in the source ZIP.

## Initial configuration

1. Log in as System Manager. Go to **Unifonic WhatsApp > UW Account > New**.
2. Create account with `Account Label`, provider `Application ID` (not PublicId), `PublicId`, and `Secret` obtained in **Unifonic Console > Developers > Applications > WhatsApp > Request Keys**.
3. Create a **unique high-entropy webhook token** (example shell command: `python -c 'import secrets; print(secrets.token_urlsafe(48))'`). Paste it into the Account Password field. Keep it out of code and screenshots.
4. Leave `Live Sending Enabled` **OFF** initially. Turn `Enabled` ON when the secret fields and application ID are configured.
5. In Unifonic Channels > WhatsApp > Webhook settings, configure inbound and message-delivery event URLs using the following scheme:

```
https://YOUR-HOST/api/method/unifonic_whatsapp.api.webhook.receive?account=YOUR_URL_ENCODED_ACCOUNT_NAME&token=YOUR_URL_ENCODED_TOKEN
```

**Important:** Unifonic's referenced webhook docs show how to supply webhook URLs but do not document a request-signature format. This app uses a 32+ character shared URL secret and strict `applicationId` checks until signed callback support is confirmed with Unifonic. HTTPS and reverse-proxy query-string log redaction are mandatory. Prefer provider-signed requests as soon as Unifonic makes an authenticated signature contract available.

6. Configure roles: Unifonic Manager can manage accounts/templates/consent; Unifonic Agent can see unassigned conversations and conversations assigned to them. Assign in **UW Conversation**, or use the manager API.
7. Open `/unifonic-inbox`, select the account and click **Sync templates** (manager). Create consent records in **UW Consent** with source/evidence and the E.164 phone number.
8. Test an inbound event, view it in the inbox, verify the service window and queued text in dry-run mode, then enable live sending after approval.

### Important constraints

- No live production test has been executed here. **API response shape / provider authentication behavior must be verified** in staging.
- `referenceId` is used for delivery correlation, not as a proven provider idempotency guarantee.
- No automatic resend on network timeout or HTTP 5xx (ambiguous outcome).
- Only **approved** templates from template sync and customers with **explicit recorded opt-in** can receive business-initiated templates.
- Unifonic documents a 24-hour customer service window after the customer's last message. The app deliberately does not automatically grant ad-driven 72-hour exceptions.
- Media received from webhooks is stored as JSON metadata; downloading/rehosting media, content scanning and public media URLs are **not implemented**.
- Agent inbox is a practical MVP, not a full WhatsApp Cloud contact center: no realtime socket, no campaigns, no AI bot, no file upload, no analytics SLA dashboard yet.
- Frappe and ERPNext are optional runtime dependencies: `required_apps` includes only Frappe. ERPNext hook handlers only run when matching ERPNext documents exist.

## Cursor

Open the project root in Cursor, read `AGENTS.md`, `docs/SRS.md`, `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, then follow `.cursor/rules/unifonic-whatsapp.mdc` and `docs/ACCEPTANCE_TESTS.md`. The recommended first task is to install on a Frappe v15 staging bench, fix any migration/build differences, and record evidence in `docs/RELEASE_CHECKLIST.md`.

## Tests

```bash
python scripts/validate_project.py
python -m compileall -q unifonic_whatsapp
cd ~/frappe-bench
bench --site your-staging.example.com run-tests --app unifonic_whatsapp
```

Docs: `docs/SRS.md`, `docs/API_CONTRACT.md`, `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/ACCEPTANCE_TESTS.md`, `docs/RELEASE_CHECKLIST.md`.
