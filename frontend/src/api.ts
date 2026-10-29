import { frappeRequest } from 'frappe-ui'
export type Account = { name: string; account_label: string; company?: string; default_language: string }
export type Conversation = { name: string; account: string; contact: string; customer_name?: string; assigned_to?: string; status: string; session_open?: boolean; last_inbound_at?: string; last_message_at?: string; last_message_preview?: string }
export type Message = { name: string; direction: string; message_type: string; text: string; status: string; creation: string; content_json?: string; error_details?: string }
export type Template = { name: string; template_name: string; language: string; category?: string; status: string; components_json: string }
const BASE = '/api/method/unifonic_whatsapp.api.inbox.'
export function api<T>(method: string, params: Record<string, unknown> = {}, httpMethod: 'GET' | 'POST' = 'GET'): Promise<T> {
  return frappeRequest({ url: BASE + method, method: httpMethod, params }) as Promise<T>
}
