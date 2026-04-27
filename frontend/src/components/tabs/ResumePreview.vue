<template>
  <div class="resume-preview">
    <div v-if="!resumeHtml?.html" class="empty-state">
      <div class="empty-mark" aria-hidden="true"></div>
      <p>简历尚未生成</p>
      <p class="hint">请先上传 JD 和个人材料</p>
    </div>

    <template v-else>
      <div class="preview-toolbar">
        <button class="toolbar-btn" @click="exportHtml" title="导出 HTML">
          导出 HTML
        </button>
        <button class="toolbar-btn" @click="exportJson" title="导出 JSON">
          导出 JSON
        </button>
        <button class="toolbar-btn" @click="exportMarkdown" title="导出 Markdown">
          导出 MD
        </button>
        <button class="toolbar-btn" @click="refreshPreview" title="刷新预览">
          刷新
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
import { exportArtifact, readApiError } from '../../api/index.js'

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
    const { data } = await exportArtifact(props.sessionId, 'resume', 'html')
    downloadBlob(data, 'resume.html', 'text/html')
  } catch (e) {
    alert('导出失败: ' + await readApiError(e))
  }
}

async function exportJson() {
  if (!props.sessionId) return
  try {
    const { data } = await exportArtifact(props.sessionId, 'resume', 'json')
    downloadBlob(data, 'resume.json', 'application/json')
  } catch (e) {
    alert('导出失败: ' + await readApiError(e))
  }
}

async function exportMarkdown() {
  if (!props.sessionId) return
  try {
    const { data } = await exportArtifact(props.sessionId, 'resume', 'md')
    downloadBlob(data, 'resume.md', 'text/markdown')
  } catch (e) {
    alert('导出失败: ' + await readApiError(e))
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
  animation: panelFadeIn 0.24s ease both;
}
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: var(--text-secondary);
}
.empty-mark {
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
  border-radius: 14px;
  background: var(--primary-soft);
  border: 1px solid var(--border);
  position: relative;
}
.empty-mark::before {
  content: '';
  position: absolute;
  left: 14px;
  top: 10px;
  width: 16px;
  height: 22px;
  border: 2px solid var(--primary);
  border-radius: 3px;
}
.empty-mark::after {
  content: '';
  position: absolute;
  left: 18px;
  top: 17px;
  width: 8px;
  height: 2px;
  background: var(--primary);
  box-shadow: 0 5px 0 var(--primary);
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
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  color: var(--primary);
  transition:
    background var(--transition),
    border-color var(--transition),
    transform var(--transition);
}
.toolbar-btn:hover {
  background: var(--primary-soft);
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.preview-frame-wrapper {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: #fff;
  min-height: 600px;
  box-shadow: var(--shadow);
}
.preview-frame {
  width: 100%;
  height: 100%;
  border: none;
  min-height: 600px;
}
</style>
