<template>
  <div class="app-layout">
    <!-- 左侧对话区 -->
    <ChatPanel
      :messages="messages"
      :loading="loading"
      @send="handleSend"
      @upload="handleUpload"
    />
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
</template>

<script setup>
import { ref } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import { sendChat } from './api/index.js'

const sessionId = ref('')
const loading = ref(false)
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
    addMessage('assistant', `❌ ${msg}`)
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
    addMessage('assistant', `❌ ${msg}`)
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
  height: 100%;
  overflow: hidden;
}
</style>
