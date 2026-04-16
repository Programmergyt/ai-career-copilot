<template>
  <div class="resume-preview">
    <div v-if="!resumeHtml?.html" class="empty-state">
      <div class="empty-icon">📄</div>
      <p>简历尚未生成</p>
      <p class="hint">请先上传 JD 和个人材料</p>
    </div>

    <template v-else>
      <div class="preview-toolbar">
        <button class="toolbar-btn" @click="exportHtml" title="导出 HTML">
          ⬇️ 导出 HTML
        </button>
        <button class="toolbar-btn" @click="exportJson" title="导出 JSON">
          📦 导出 JSON
        </button>
        <button class="toolbar-btn" @click="refreshPreview" title="刷新预览">
          🔄 刷新
        </button>
      </div>
      <div class="preview-frame-wrapper">
        <iframe
          ref="previewFrame"
          class="preview-frame"
          sandbox="allow-same-origin"
          :srcdoc="resumeHtml.html"
        ></iframe>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { exportResume } from '../../api/index.js'

const props = defineProps({
  resumeHtml: Object,
  sessionId: String,
})

const previewFrame = ref(null)

function refreshPreview() {
  if (previewFrame.value) {
    previewFrame.value.srcdoc = props.resumeHtml?.html || ''
  }
}

async function exportHtml() {
  if (!props.sessionId) return
  try {
    const { data } = await exportResume(props.sessionId, 'html')
    downloadBlob(data, 'resume.html', 'text/html')
  } catch (e) {
    alert('导出失败: ' + (e.response?.data?.detail || e.message))
  }
}

async function exportJson() {
  if (!props.sessionId) return
  try {
    const { data } = await exportResume(props.sessionId, 'json')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    downloadBlob(blob, 'resume.json', 'application/json')
  } catch (e) {
    alert('导出失败: ' + (e.response?.data?.detail || e.message))
  }
}

function downloadBlob(blob, filename, type) {
  const b = blob instanceof Blob ? blob : new Blob([blob], { type })
  const url = URL.createObjectURL(b)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.resume-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-secondary);
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.hint {
  font-size: 13px;
  color: var(--text-light);
  margin-top: 6px;
}

.preview-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.toolbar-btn {
  padding: 6px 14px;
  background: var(--bg);
  border-radius: var(--radius);
  font-size: 13px;
  color: var(--text);
  transition: all var(--transition);
}
.toolbar-btn:hover {
  background: var(--border);
}

.preview-frame-wrapper {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: #fff;
  min-height: 600px;
}
.preview-frame {
  width: 100%;
  height: 100%;
  border: none;
  min-height: 600px;
}
</style>
