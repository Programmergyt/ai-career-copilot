<template>
  <div class="chat-panel">
    <div class="chat-header">
      <h2>💬 AI Career Copilot</h2>
    </div>

    <!-- 消息列表 -->
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="chat-empty">
        <div class="empty-icon">🚀</div>
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
          {{ msg.role === 'user' ? '👤' : '🤖' }}
        </div>
        <div class="message-body">
          <div class="message-content" v-html="renderContent(msg.content)"></div>
          <div v-if="msg.attachments?.length" class="message-attachments">
            <span v-for="(a, i) in msg.attachments" :key="i" class="attachment-tag">
              📎 {{ a }}
            </span>
          </div>
          <div class="message-time">{{ msg.time }}</div>
        </div>
      </div>

      <div v-if="loading" class="message-item assistant">
        <div class="message-avatar">🤖</div>
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
          📎 {{ f.filename }}
          <button class="remove-file" @click="removeFile(i)">×</button>
        </div>
      </div>

      <div class="input-row">
        <label class="upload-btn" title="上传附件">
          📁
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
          {{ loading ? '⏳' : '➤' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
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
  // Simple: replace newlines with <br>, escape html
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
  return DOMPurify(escaped)
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
  width: 420px;
  min-width: 360px;
  display: flex;
  flex-direction: column;
  background: var(--bg-white);
  border-right: 1px solid var(--border);
}

.chat-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.chat-header h2 {
  font-size: 18px;
  font-weight: 600;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.chat-empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-secondary);
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
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
}
.message-item.user {
  flex-direction: row-reverse;
}
.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  flex-shrink: 0;
}
.message-body {
  max-width: 80%;
}
.message-content {
  background: var(--bg);
  padding: 10px 14px;
  border-radius: var(--radius);
  line-height: 1.6;
  word-break: break-word;
}
.message-item.user .message-content {
  background: var(--primary);
  color: #fff;
}
.message-attachments {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.attachment-tag {
  font-size: 12px;
  background: #eef2ff;
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 4px;
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
  background: var(--bg);
  border-radius: var(--radius);
}
.typing-indicator span {
  width: 8px;
  height: 8px;
  background: var(--text-light);
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
  padding: 12px 16px;
  flex-shrink: 0;
}
.pending-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}
.pending-file-tag {
  font-size: 12px;
  background: #eef2ff;
  color: var(--primary);
  padding: 4px 10px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.remove-file {
  background: none;
  color: var(--danger);
  font-size: 14px;
  padding: 0 2px;
}
.input-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.upload-btn {
  font-size: 20px;
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius);
  transition: background var(--transition);
}
.upload-btn:hover {
  background: var(--bg);
}
.input-row textarea {
  flex: 1;
  resize: none;
  padding: 8px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  line-height: 1.5;
  max-height: 120px;
  transition: border-color var(--transition);
}
.input-row textarea:focus {
  border-color: var(--primary);
}
.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition);
}
.send-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}
.send-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
