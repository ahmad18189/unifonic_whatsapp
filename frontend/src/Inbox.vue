<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { api, type Account, type Conversation, type Message, type Template } from './api'

const accounts = ref<Account[]>([])
const selectedAccount = ref('')
const conversations = ref<Conversation[]>([])
const selectedConversation = ref<Conversation | null>(null)
const messages = ref<Message[]>([])
const templates = ref<Template[]>([])
const search = ref('')
const reply = ref('')
const templateName = ref('')
const templatePhone = ref('')
const componentsJson = ref('[]')
const showTemplate = ref(false)
const sending = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
let timer: ReturnType<typeof setInterval> | undefined
const availableTemplates = computed(() => templates.value.filter(t => t.status === 'APPROVED'))
const selectedTemplate = computed(() => availableTemplates.value.find(t => t.name === templateName.value))
// The server computes the service window in the Frappe site timezone.
const canReply = computed(() => Boolean(selectedConversation.value?.session_open))
function showError(e: unknown) { error.value = e instanceof Error ? e.message : String(e) }

async function init() {
  busy.value = true
  try {
    accounts.value = await api<Account[]>('accounts')
    if (!selectedAccount.value && accounts.value.length) selectedAccount.value = accounts.value[0].name
    await loadConversations()
  } catch (e) { showError(e) } finally { busy.value = false }
}
async function loadConversations() {
  if (!selectedAccount.value) return
  try {
    conversations.value = await api<Conversation[]>('conversations', { account: selectedAccount.value, search: search.value })
    if (selectedConversation.value) {
      const fresh = conversations.value.find(c => c.name === selectedConversation.value?.name)
      if (fresh) selectedConversation.value = fresh
    }
  } catch (e) { showError(e) }
}
async function selectConversation(conversation: Conversation) {
  selectedConversation.value = conversation
  error.value = ''
  await loadMessages()
}
async function loadMessages() {
  if (!selectedConversation.value) return
  try {
    const result = await api<Message[]>('messages', { conversation: selectedConversation.value.name })
    messages.value = result.reverse()
  } catch (e) { showError(e) }
}
async function loadTemplates() {
  if (!selectedAccount.value) return
  try { templates.value = await api<Template[]>('templates', { account: selectedAccount.value }) }
  catch (e) { showError(e) }
}
async function sendText() {
  if (!selectedConversation.value || !reply.value.trim() || sending.value) return
  sending.value = true; error.value = ''; notice.value = ''
  try {
    await api('send_text', { conversation: selectedConversation.value.name, text: reply.value.trim() }, 'POST')
    reply.value = ''
    await loadMessages(); await loadConversations()
  } catch (e) { showError(e) } finally { sending.value = false }
}
async function sendTemplate() {
  if (!selectedTemplate.value || !templatePhone.value) return
  sending.value = true; error.value = ''; notice.value = ''
  try {
    JSON.parse(componentsJson.value)
    await api('send_template', { account: selectedAccount.value, phone: templatePhone.value,
      template_name: selectedTemplate.value.template_name, language: selectedTemplate.value.language,
      components_json: componentsJson.value }, 'POST')
    showTemplate.value = false; notice.value = 'Template queued (live sending may be disabled).'
    await loadConversations()
  } catch (e) { showError(e) } finally { sending.value = false }
}
async function syncTemplates() {
  error.value = ''; notice.value = ''
  try {
    const response = await api<{synced: number}>('sync_templates', { account: selectedAccount.value }, 'POST')
    notice.value = `Synced ${response.synced} templates.`; await loadTemplates()
  } catch (e) { showError(e) }
}
async function setStatus(status: string) {
  if (!selectedConversation.value) return
  try {
    await api('resolve', { conversation: selectedConversation.value.name, status }, 'POST')
    await loadConversations()
  } catch (e) { showError(e) }
}
function openTemplates() {
  showTemplate.value = true
  templatePhone.value = selectedConversation.value?.contact ?? ''
  loadTemplates()
}
watch(selectedAccount, () => { selectedConversation.value = null; messages.value = []; loadConversations(); loadTemplates() })
watch(search, loadConversations)
onMounted(async () => {
  await init()
  timer = setInterval(async () => { if (document.visibilityState === 'visible') { await loadConversations(); await loadMessages() } }, 10000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div><strong>Unifonic WhatsApp</strong><small>Frappe v15 · Shared Inbox</small></div>
      <div class="topbar-actions"><a href="/app" target="_blank" rel="noreferrer">Frappe Desk</a><button @click="loadConversations">Refresh</button></div>
    </header>
    <div v-if="error" class="alert error" role="alert">{{ error }} <button @click="error = ''">Dismiss</button></div>
    <div v-if="notice" class="alert good">{{ notice }} <button @click="notice = ''">Dismiss</button></div>
    <div class="workspace">
      <aside class="sidebar">
        <div class="aside-top">
          <select v-model="selectedAccount" aria-label="WhatsApp account"><option value="" disabled>Select account</option><option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.account_label }}</option></select>
          <input v-model="search" placeholder="Search phone number" aria-label="Search phone" />
          <div class="side-buttons"><button @click="openTemplates" :disabled="!selectedAccount">New template</button><button @click="syncTemplates" :disabled="!selectedAccount">Sync templates</button></div>
        </div>
        <div class="conversation-list">
          <button v-for="c in conversations" :key="c.name" class="conversation" :class="{ active: selectedConversation?.name === c.name }" @click="selectConversation(c)">
            <span class="avatar">{{ (c.customer_name || c.contact).slice(0, 1).toUpperCase() }}</span>
            <span class="conversation-details"><strong>{{ c.customer_name || c.contact }}</strong><small>{{ c.contact }} · {{ c.status }}</small><span class="preview">{{ c.last_message_preview || 'No messages yet' }}</span></span>
          </button>
          <p v-if="!busy && conversations.length === 0" class="empty">No conversations for this account.</p>
        </div>
      </aside>
      <main class="chat" v-if="selectedConversation">
        <div class="chat-header"><div><strong>{{ selectedConversation.customer_name || selectedConversation.contact }}</strong><small>{{ selectedConversation.contact }} · {{ selectedConversation.assigned_to || 'Unassigned' }}</small></div>
          <div class="inline"><button @click="setStatus(selectedConversation.status === 'Open' ? 'Resolved' : 'Open')">{{ selectedConversation.status === 'Open' ? 'Resolve' : 'Reopen' }}</button><button @click="openTemplates">Template</button></div></div>
        <div class="message-list">
          <div v-for="m in messages" :key="m.name" class="bubble" :class="m.direction === 'Outbound' ? 'outgoing' : 'incoming'">
            <span class="message-type" v-if="m.message_type !== 'text'">{{ m.message_type }}</span>
            <p>{{ m.text }}</p><small>{{ m.status }} · {{ m.creation }}</small>
            <small v-if="m.error_details" class="warn">{{ m.error_details }}</small>
          </div>
          <p v-if="!messages.length" class="empty">No messages yet</p>
        </div>
        <div class="compose">
          <small v-if="!canReply" class="warn">Free-form reply unavailable: no active 24-hour inbound window. Use an approved template.</small>
          <div class="compose-line"><textarea v-model="reply" placeholder="Write your reply..." :disabled="!canReply || sending" maxlength="4096" @keydown.ctrl.enter.prevent="sendText" rows="2"></textarea><button class="primary" :disabled="!canReply || !reply.trim() || sending" @click="sendText">Send</button></div>
        </div>
      </main>
      <main class="chat blank" v-else><h2>Choose a conversation</h2><p>Incoming WhatsApp messages will appear here after webhook configuration.</p></main>
    </div>
    <div v-if="showTemplate" class="overlay" @click.self="showTemplate = false">
      <section class="modal" role="dialog" aria-modal="true" aria-label="Send approved template">
        <header><h3>Send approved template</h3><button @click="showTemplate = false">Close</button></header>
        <label>Recipient (E.164)</label><input v-model="templatePhone" placeholder="+9665XXXXXXXX" />
        <label>Approved template</label><select v-model="templateName"><option value="" disabled>Select template</option><option v-for="t in availableTemplates" :key="t.name" :value="t.name">{{ t.template_name }} ({{ t.language }})</option></select>
        <label>Components JSON (provider-compatible)</label><textarea v-model="componentsJson" rows="6" spellcheck="false"></textarea>
        <p class="hint">Requires recorded opt-in and an approved synced template. Match body/header variable positions exactly.</p>
        <button class="primary" :disabled="!templateName || !templatePhone || sending" @click="sendTemplate">Queue template</button>
      </section>
    </div>
  </div>
</template>
