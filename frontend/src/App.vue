<template>
  <div class="app-layout">
    <div class="mobile-tabs" role="tablist" aria-label="面板切换">
      <button
        type="button"
        class="mobile-tab"
        :class="{ active: activePanel === 'chat' }"
        :aria-selected="activePanel === 'chat'"
        @click="activePanel = 'chat'"
      >
        对话
      </button>
      <button
        type="button"
        class="mobile-tab"
        :class="{ active: activePanel === 'result' }"
        :aria-selected="activePanel === 'result'"
        @click="activePanel = 'result'"
      >
        结果
      </button>
    </div>

    <div
      class="layout-pane chat-pane"
      :class="{ 'is-hidden-mobile': activePanel !== 'chat' }"
    >
      <!-- 左侧对话区 -->
      <ChatPanel
        :messages="messages"
        :loading="loading"
        @send="handleSend"
        @upload="handleUpload"
      />
    </div>

    <div
      class="layout-pane result-pane"
      :class="{ 'is-hidden-mobile': activePanel !== 'result' }"
    >
      <!-- 右侧结果面板 -->
      <ResultPanel
        :session-id="sessionId"
        :job="job"
        :gaps="gaps"
        :questions="questionsToAsk"
        :resume-html="resumeHtml"
        :resume-content="resumeContentJson"
        :render-config="renderConfig"
        :interview-qa="interviewQa"
        :triggered-agents="triggeredAgents"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import { sendChat } from './api/index.js'

const sessionId = ref('')
const loading = ref(false)
const activePanel = ref('chat')
const messages = ref([])

// State from backend
const job = ref(null)
const gaps = ref([])
const questionsToAsk = ref([])
const resumeContentJson = ref(null)
const renderConfig = ref(null)
const resumeHtml = ref(null)
const interviewQa = ref([])
const triggeredAgents = ref([])

function addMessage(role, content, attachments = []) {
  messages.value.push({
    id: Date.now(),
    role,
    content,
    attachments,
    time: new Date().toLocaleTimeString(),
  })
}

async function handleSend(text) {
  if (!text.trim()) return
  addMessage('user', text)
  loading.value = true

  try {
    const { data } = await sendChat(sessionId.value, text)
    applyResponse(data)
    addMessage('assistant', data.reply_message || '处理完成。')
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    addMessage('assistant', `请求失败：${msg}`)
  } finally {
    loading.value = false
  }
}

async function handleUpload({ text, attachments }) {
  addMessage('user', text || '（上传附件）', attachments.map(a => a.filename))
  loading.value = true

  const payloadAttachments = attachments.map(a => ({
    filename: a.filename,
    content: a.content,
    content_encoding: 'base64',
  }))

  try {
    const { data } = await sendChat(sessionId.value, text, payloadAttachments)
    applyResponse(data)
    addMessage('assistant', data.reply_message || '附件处理完成。')
  } catch (err) {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    addMessage('assistant', `请求失败：${msg}`)
  } finally {
    loading.value = false
  }
}

function applyResponse(data) {
  sessionId.value = data.session_id
  if (data.job) job.value = data.job
  if (data.gaps) gaps.value = data.gaps
  if (data.questions_to_ask) questionsToAsk.value = data.questions_to_ask
  if (data.resume_content_json) resumeContentJson.value = data.resume_content_json
  if (data.render_config) renderConfig.value = data.render_config
  if (data.resume_html) resumeHtml.value = data.resume_html
  if (data.interview_qa) interviewQa.value = data.interview_qa
  if (data.triggered_agents) triggeredAgents.value = data.triggered_agents
}
</script>

<style scoped>
.app-layout {
  display: flex;
  width: 100%;
  height: 100dvh;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(232, 240, 254, 0.82) 0%, rgba(237, 244, 255, 0.96) 100%),
    var(--bg);
}

.mobile-tabs {
  display: none;
}

.layout-pane {
  flex: 0 0 50%;
  width: 50%;
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chat-pane {
  border-right: 1px solid var(--border);
  box-shadow: 8px 0 24px rgba(39, 83, 138, 0.05);
  z-index: 1;
}

.result-pane {
  background: var(--bg-white);
}

@media (max-width: 900px) {
  :global(html),
  :global(body),
  :global(#app) {
    overflow-x: hidden;
  }

  .app-layout {
    flex-direction: column;
    overflow-x: hidden;
  }

  .mobile-tabs {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
    margin: 10px 12px;
    padding: 4px;
    border: 1px solid rgba(229, 231, 235, 0.9);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.92);
    box-shadow: var(--shadow);
    backdrop-filter: blur(12px);
  }

  .mobile-tab {
    flex: 1;
    min-width: 0;
    padding: 9px 14px;
    border-radius: 999px;
    background: transparent;
    color: var(--text-secondary);
    font-weight: 600;
    transition:
      background var(--transition),
      color var(--transition),
      box-shadow var(--transition);
  }

  .mobile-tab.active {
    background: var(--primary);
    color: #fff;
    box-shadow: 0 4px 14px rgba(26, 115, 232, 0.22);
  }

  .layout-pane {
    flex: 1 1 auto;
    width: 100%;
    height: auto;
    min-height: 0;
  }

  .chat-pane {
    border-right: 0;
  }

  .layout-pane.is-hidden-mobile {
    display: none;
  }
}
</style>
