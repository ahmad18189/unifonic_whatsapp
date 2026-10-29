# Runbook: Deployment, monitoring, recovery

## Components
Frappe v15 web + Redis queues + scheduler, MariaDB, Vue/Frappe UI static bundle, HTTPS reverse proxy, Unifonic WhatsApp account.

## Required checks
- `bench --site SITE list-apps` shows `unifonic_whatsapp`.
- `bench --site SITE migrate` completed without errors.
- `bench --site SITE doctor` shows scheduler and worker healthy.
- UW Account enabled, secrets protected, correct `application_id`, live sending OFF until go-live.
- GET `/unifonic-inbox` as authenticated agent returns frontend; guest redirected to login.
- POST webhook with wrong token -> refused; correct token & exact app ID -> event stored.
- API client can reach `https://apis.unifonic.com/v1` using TLS.

## Monitor
- `UW Webhook Event`: status Failed / Pending Match and attempts >= 8 need human attention.
- `UW Message`: status Unknown or Sending > 30 min must be reconciled; **do not manually requeue** without confirming provider never received it.
- `UW Message`: status Failed identify invalid numbers, template approval, invalid credentials.
- RQ workers: `short` queue depth and errors. Daily check unprocessed journal counts.
- Unifonic account quality/template events. Check templates after Unifonic approval/pauses.

## Recovery: inbound event missing
Check Unifonic Channels > WhatsApp webhook URL/events; verify TLS and query-string redaction; confirm correct applicationId; inspect raw UW Webhook Event (manager). Run `bench --site SITE execute unifonic_whatsapp.jobs.recover_events`. Use `replay_unmatched` for status that arrived before send acknowledgment. No need to replay if event already Processed.

## Recovery: Unknown outbound
Search UW Message by local referenceId and provider message ID. Run `bench --site SITE execute unifonic_whatsapp.jobs.reconcile_unknown`. If status not found, keep Unknown, raise support ticket with Unifonic; never send again automatically. Before operator requeue, establish proof provider did **not** accept it.

## Restore
Restore Frappe database/files via normal `bench restore` workflow to same app version. Restore API secrets using Frappe's encryption key strategy. Redeploy frontend assets. Disable live sending during restore/reconciliation to avoid duplicate queue effects. Check post-restore worker backlog before enabling.

## Rotate credentials
Unifonic Console -> request/rotate keys under Developer > Applications; update UW Account Password field; test GET template list. For token rotation, set new token and update both Unifonic inbound/delivery webhook URLs. Enable log scrubbing while validating.

## Disable emergency sending
Set `live_sending_enabled=0` on all UW Accounts (manager Desk); note that already in-flight POSTs cannot be recalled. Stop RQ workers or block outbound egress if required by incident response. Incoming events can still be accepted.

## Upgrade
Staging first; take backups; test migrations, queue claim, API and frontend; deploy branch/tag; `bench --site SITE migrate`; `bench build --app unifonic_whatsapp`; restart and clear cache. Rollback requires DB compatibility validation.
