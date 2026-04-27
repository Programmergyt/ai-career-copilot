<template>
  <div class="chat-panel">
    <div class="chat-header">
      <h2><span class="brand-mark" aria-hidden="true"></span>AI Career Copilot</h2>
    </div>

    <!-- 消息列表 -->
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="chat-empty">
        <div class="empty-mark" aria-hidden="true"></div>
        <p>开始对话吧！你可以：</p>
        <ul>
          <li>粘贴或上传 JD（岗位描述）</li>
          <li>上传个人材料（PDF / DOCX / TXT / MD）</li>
          <li>输入个人信息补充</li>
        </ul>
      </div>

      <div
        v-for="msg in messages"
        :key="msg.id"
        class="message-item"
        :class="msg.role"
      >
        <div class="message-avatar">
          {{ msg.role === 'user' ? '我' : 'AI' }}
        </div>
        <div class="message-body">
          <div class="message-content" v-html="renderContent(msg.content)"></div>
          <div v-if="msg.attachments?.length" class="message-attachments">
            <span v-for="(a, i) in msg.attachments" :key="i" class="attachment-tag">
              {{ a }}
            </span>
          </div>
          <div class="message-time">{{ msg.time }}</div>
        </div>
      </div>

      <div v-if="loading" class="message-item assistant">
        <div class="message-avatar">AI</div>
        <div class="message-body">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="chat-input-area">
      <!-- 附件预览 -->
      <div v-if="pendingFiles.length" class="pending-files">
        <div v-for="(f, i) in pendingFiles" :key="i" class="pending-file-tag">
          {{ f.filename }}
          <button class="remove-file" @click="removeFile(i)">×</button>
        </div>
      </div>

      <div class="input-row">
        <label class="upload-btn" title="上传附件">
          附件
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md"
            @change="onFileSelect"
            style="display:none"
          />
        </label>
        <textarea
          ref="inputEl"
          v-model="inputText"
          placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
          rows="1"
          @keydown="onKeydown"
          @input="autoResize"
        ></textarea>
        <button class="send-btn" @click="doSend" :disabled="loading">
          {{ loading ? '发送中' : '发送' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import { marked } from 'marked'
import DOMPurify from '../utils/purify.js'

const props = defineProps({
  messages: Array,
  loading: Boolean,
})

const emit = defineEmits(['send', 'upload'])

const inputText = ref('')
const pendingFiles = ref([])
const messagesContainer = ref(null)
const inputEl = ref(null)
const renderCache = new Map()
const maxCacheSize = 120

marked.use({
  gfm: true,
  breaks: true,
})

// Auto-scroll on new messages
watch(
  () => props.messages.length,
  () => nextTick(() => scrollToBottom()),
)
watch(
  () => props.loading,
  () => nextTick(() => scrollToBottom()),
)

function scrollToBottom() {
  const el = messagesContainer.value
  if (el) el.scrollTop = el.scrollHeight
}

function renderContent(text) {
  if (!text) return ''
  const cacheKey = String(text)

  if (renderCache.has(cacheKey)) return renderCache.get(cacheKey)

  const html = marked.parse(cacheKey)
  const cleanHtml = DOMPurify(html)

  renderCache.set(cacheKey, cleanHtml)
  if (renderCache.size > maxCacheSize) {
    renderCache.delete(renderCache.keys().next().value)
  }

  return cleanHtml
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    doSend()
  }
}

function autoResize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function doSend() {
  if (props.loading) return
  const text = inputText.value.trim()

  if (pendingFiles.value.length > 0) {
    emit('upload', { text, attachments: [...pendingFiles.value] })
    pendingFiles.value = []
  } else if (text) {
    emit('send', text)
  } else {
    return
  }
  inputText.value = ''
  nextTick(() => autoResize())
}

function onFileSelect(e) {
  const files = Array.from(e.target.files)
  for (const file of files) {
    const reader = new FileReader()
    reader.onload = () => {
      const base64 = reader.result.split(',')[1]
      pendingFiles.value.push({
        filename: file.name,
        content: base64,
      })
    }
    reader.readAsDataURL(file)
  }
  e.target.value = ''
}

function removeFile(index) {
  pendingFiles.value.splice(index, 1)
}
</script>

<style scoped>
.chat-panel {
  width: 100%;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-white);
}

.chat-header {
  padding: 18px 22px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.96);
}
.chat-header h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 600;
  letter-spacing: 0;
}
.brand-mark {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--primary);
  box-shadow: 0 0 0 5px var(--primary-soft);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
  background: linear-gradient(180deg, #ffffff 0%, var(--surface) 100%);
}

.chat-empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
  animation: panelFadeIn 0.28s ease both;
}
.empty-mark {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  border-radius: 16px;
  background:
    linear-gradient(135deg, var(--primary) 0%, #6ea8ff 100%);
  box-shadow: 0 10px 24px rgba(26, 115, 232, 0.18);
  position: relative;
}
.empty-mark::after {
  content: '';
  position: absolute;
  inset: 13px;
  border: 2px solid rgba(255, 255, 255, 0.86);
  border-radius: 10px;
}
.chat-empty ul {
  text-align: left;
  display: inline-block;
  margin-top: 8px;
}
.chat-empty li {
  margin: 4px 0;
}

.message-item {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  animation: panelFadeIn 0.22s ease both;
}
.message-item.user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--primary-soft);
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.message-body {
  max-width: 80%;
}
.message-content {
  background: #fff;
  border: 1px solid var(--border);
  padding: 10px 14px;
  border-radius: var(--radius);
  line-height: 1.6;
  word-break: break-word;
  box-shadow: var(--shadow);
}
.message-content :deep(*) {
  max-width: 100%;
}
.message-content :deep(p) {
  margin: 0 0 8px;
}
.message-content :deep(p:last-child),
.message-content :deep(ul:last-child),
.message-content :deep(ol:last-child),
.message-content :deep(pre:last-child),
.message-content :deep(blockquote:last-child),
.message-content :deep(table:last-child) {
  margin-bottom: 0;
}
.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3),
.message-content :deep(h4),
.message-content :deep(h5),
.message-content :deep(h6) {
  margin: 12px 0 8px;
  color: var(--text);
  font-weight: 700;
  line-height: 1.35;
}
.message-content :deep(h1) { font-size: 20px; }
.message-content :deep(h2) { font-size: 18px; }
.message-content :deep(h3) { font-size: 16px; }
.message-content :deep(h4),
.message-content :deep(h5),
.message-content :deep(h6) { font-size: 14px; }
.message-content :deep(ul),
.message-content :deep(ol) {
  margin: 0 0 10px;
  padding-left: 20px;
}
.message-content :deep(li) {
  margin: 3px 0;
}
.message-content :deep(a) {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}
.message-content :deep(a:hover) {
  text-decoration: underline;
}
.message-content :deep(blockquote) {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 3px solid var(--primary);
  border-radius: 0 var(--radius) var(--radius) 0;
  background: var(--primary-subtle);
  color: var(--text-secondary);
}
.message-content :deep(code) {
  padding: 2px 5px;
  border-radius: 5px;
  background: var(--primary-soft);
  color: var(--primary-hover);
  font-family: ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace;
  font-size: 0.92em;
  word-break: break-word;
}
.message-content :deep(pre) {
  margin: 10px 0;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #f7faff;
  overflow-x: auto;
  white-space: pre;
}
.message-content :deep(pre code) {
  display: block;
  min-width: max-content;
  padding: 0;
  background: transparent;
  color: var(--text);
  line-height: 1.55;
  word-break: normal;
}
.message-content :deep(table) {
  display: block;
  width: 100%;
  margin: 10px 0;
  border-collapse: collapse;
  overflow-x: auto;
  white-space: nowrap;
}
.message-content :deep(th),
.message-content :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
}
.message-content :deep(th) {
  background: var(--primary-subtle);
  color: var(--text);
  font-weight: 600;
}
.message-content :deep(hr) {
  height: 1px;
  margin: 12px 0;
  border: 0;
  background: var(--border);
}
.message-item.user .message-content {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.message-item.user .message-content :deep(h1),
.message-item.user .message-content :deep(h2),
.message-item.user .message-content :deep(h3),
.message-item.user .message-content :deep(h4),
.message-item.user .message-content :deep(h5),
.message-item.user .message-content :deep(h6),
.message-item.user .message-content :deep(a) {
  color: #fff;
}
.message-item.user .message-content :deep(blockquote) {
  border-left-color: rgba(255, 255, 255, 0.78);
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.92);
}
.message-item.user .message-content :deep(code) {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}
.message-item.user .message-content :deep(pre) {
  border-color: rgba(255, 255, 255, 0.22);
  background: rgba(0, 0, 0, 0.12);
}
.message-item.user .message-content :deep(pre code) {
  color: #fff;
}
.message-item.user .message-content :deep(th) {
  background: rgba(255, 255, 255, 0.16);
  color: #fff;
}
.message-item.user .message-content :deep(th),
.message-item.user .message-content :deep(td) {
  border-color: rgba(255, 255, 255, 0.24);
}
.message-attachments {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.attachment-tag {
  font-size: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  padding: 3px 8px;
  border-radius: 999px;
}
.message-time {
  font-size: 11px;
  color: var(--text-light);
  margin-top: 4px;
}
.message-item.user .message-time {
  text-align: right;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--primary);
  border-radius: 50%;
  animation: typing 1.2s infinite;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

/* Input area */
.chat-input-area {
  border-top: 1px solid var(--border);
  padding: 14px 18px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.98);
}
.pending-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.pending-file-tag {
  font-size: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  padding: 5px 10px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.remove-file {
  background: none;
  color: var(--text-light);
  font-size: 14px;
  padding: 0 2px;
}
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.upload-btn {
  min-height: 40px;
  cursor: pointer;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--primary);
  background: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  transition:
    background var(--transition),
    border-color var(--transition),
    transform var(--transition);
}
.upload-btn:hover {
  background: var(--primary-soft);
  border-color: var(--border-strong);
  transform: translateY(-1px);
}
.input-row textarea {
  flex: 1;
  resize: none;
  min-width: 0;
  padding: 9px 13px;
  border-radius: 18px;
  border: 1px solid var(--border);
  line-height: 1.5;
  max-height: 120px;
  background: var(--surface);
  transition:
    border-color var(--transition),
    background var(--transition),
    box-shadow var(--transition);
}
.input-row textarea:focus {
  border-color: var(--primary);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.12);
}
.send-btn {
  min-width: 64px;
  height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  background: var(--primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  transition:
    background var(--transition),
    transform var(--transition),
    box-shadow var(--transition);
}
.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
  box-shadow: 0 8px 18px rgba(26, 115, 232, 0.18);
  transform: translateY(-1px);
}
.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
