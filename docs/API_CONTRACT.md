# Unifonic Conversations API contract (verified 2026-10-29)

## Canonical base and auth
- Base: `https://apis.unifonic.com/v1`
- Outbound headers: `PublicId`, `Secret`, `Content-Type: application/json`
- `POST /messages`: recipient `{contact:"+966...",channel:"whatsapp"}` and content object.
- `GET /messages/status?messageIds=<csv>`
- `GET /messages/status_by_ref_id?referenceIds=<csv>` (only when `referenceId` set on outbound)
- `GET /whatsapp/message_templates` returns a list with `name`, `language`, `status`, `category`, `components`.

## Request examples
Session text:

```json
{"recipient":{"contact":"+966500000001","channel":"whatsapp"},"content":{"type":"text","text":"Hello"},"referenceId":"LOCAL-UNIQUE-ID"}
```

Approved template with body variable:

```json
{"recipient":{"contact":"+966500000001","channel":"whatsapp"},"content":{"type":"template","name":"sandbox_account_update","language":{"code":"en"},"components":[{"type":"body","parameters":[{"type":"text","text":"Customer"}]}]},"referenceId":"LOCAL-UNIQUE-ID"}
```

Incoming text webhook example: `examples/webhook_inbound.json`. Delivery webhook example: `examples/webhook_delivered.json`.

## Event fields
Unifonic documents `eventId`, `eventType`, `applicationId`, `messageId`, `conversationId`, `sender.contact` for incoming, `recipient.contact` for outbound statuses, `content.type`, `content.text`, `content.attachments`, `timestamp`.
- `message.received` -> create inbound message and update 24-hour window.
- `message.sent`, `message.sent_successfully_to_provider`, `message.delivered`, `message.read`, `message.rejected` -> update outbound status.
- `message.template_status_update` -> update cached template approval state; do not broadcast event.
- Other account-status/quality messages may be retained without mutation.

## Undocumented / to verify
- **Webhook signature:** no HMAC/signature algorithm established from supplied provider docs. This implementation uses URL secret + application matching; confirm with Unifonic.
- **POST success response envelope:** do not hardcode `messageId` top-level. Code accepts common wrapper shapes but captures confirmation via webhook/status as fallback.
- **Idempotency:** `referenceId` is documented for status retrieval, not as a guarantee of deduplicated provider delivery.
- **Sandbox-specific base URL or test credentials:** obtain from your Unifonic account. Do not infer a fake sandbox host.
- **Webhook retry behavior:** not specified reliably. Journal and replay locally.

## Official references
1. https://docs.unifonic.com/articles/products-documentation/getting-your-api-access
2. https://docs.unifonic.com/articles/api-documentation/api-1
3. https://docs.unifonic.com/articles/products-documentation/incoming-whatsapp-messages/
4. https://docs.unifonic.com/articles/products-documentation/message-delivery-status/
5. https://docs.unifonic.com/articles/products-documentation/whatsapp-session-messages
6. https://docs.unifonic.com/articles/products-documentation/whatsapp-management-apis/
7. https://docs.unifonic.com/articles/products-documentation/whatsapp-template-messages/
