<template>
  <div class="interview-panel">
    <div v-if="!interviewQa?.length" class="empty-state">
      <div class="empty-mark" aria-hidden="true"></div>
      <p>面试问答尚未生成</p>
      <p class="hint">完成简历内容生成后，系统将自动生成面试题</p>
    </div>

    <template v-else>
      <div class="toolbar">
        <button class="toolbar-btn" @click="download('txt')">导出 TXT</button>
        <button class="toolbar-btn" @click="download('json')">导出 JSON</button>
        <button class="toolbar-btn" @click="download('md')">导出 MD</button>
      </div>

      <div class="qa-count">共 {{ interviewQa.length }} 道面试题</div>
      <div
        v-for="(qa, i) in interviewQa"
        :key="qa.id || i"
        class="qa-card"
      >
        <div class="qa-header" @click="toggleQa(i)">
          <span class="qa-index">Q{{ i + 1 }}</span>
          <span v-if="qa.category || qa.type" class="qa-type">{{ qa.category || qa.type }}</span>
          <span class="qa-question">{{ qa.question }}</span>
          <span class="qa-toggle">{{ expandedSet.has(i) ? '▲' : '▼' }}</span>
        </div>
        <div v-if="expandedSet.has(i)" class="qa-answer">
          <div class="answer-label">参考答案：</div>
          <p>{{ qa.answer || qa.reference_answer }}</p>
          <div v-if="qa.key_points?.length" class="key-points">
            <div class="answer-label">要点：</div>
            <ul>
              <li v-for="(p, j) in qa.key_points" :key="j">{{ p }}</li>
            </ul>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { exportArtifact, readApiError } from '../../api/index.js'

const props = defineProps({
  interviewQa: Array,
  sessionId: String,
})

const expandedSet = reactive(new Set())

async function download(format) {
  if (!props.sessionId || !props.interviewQa?.length) return
  try {
    const { data } = await exportArtifact(props.sessionId, 'interview', format)
    downloadBlob(data, `interview-qa.${format === 'md' ? 'md' : format}`, format)
  } catch (e) {
    alert('导出失败: ' + await readApiError(e))
  }
}

function downloadBlob(blob, filename, format) {
  const mediaType = format === 'json' ? 'application/json' : format === 'md' ? 'text/markdown' : 'text/plain'
  const fileBlob = blob instanceof Blob ? blob : new Blob([blob], { type: mediaType })
  const url = URL.createObjectURL(fileBlob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function toggleQa(index) {
  if (expandedSet.has(index)) {
    expandedSet.delete(index)
  } else {
    expandedSet.add(index)
  }
}
</script>

<style scoped>
.interview-panel {
  max-width: 720px;
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
  left: 17px;
  top: 10px;
  width: 10px;
  height: 17px;
  border: 2px solid var(--primary);
  border-radius: 999px;
}
.empty-mark::after {
  content: '';
  position: absolute;
  left: 21px;
  top: 28px;
  width: 2px;
  height: 7px;
  background: var(--primary);
}
.hint {
  font-size: 13px;
  color: var(--text-light);
  margin-top: 6px;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.toolbar-btn {
  padding: 6px 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 12px;
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

.qa-count {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.qa-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
  box-shadow: var(--shadow);
  transition:
    border-color var(--transition),
    box-shadow var(--transition),
    transform var(--transition);
}
.qa-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}
.qa-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: background var(--transition);
}
.qa-header:hover {
  background: var(--primary-subtle);
}
.qa-index {
  font-weight: 700;
  color: var(--primary);
  font-size: 13px;
  flex-shrink: 0;
}
.qa-type {
  font-size: 11px;
  background: var(--primary-soft);
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 999px;
  flex-shrink: 0;
}
.qa-question {
  flex: 1;
  font-size: 14px;
  line-height: 1.5;
}
.qa-toggle {
  color: var(--text-light);
  font-size: 12px;
  flex-shrink: 0;
}

.qa-answer {
  padding: 0 14px 14px 14px;
  border-top: 1px solid var(--border);
}
.answer-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 10px 0 6px;
}
.qa-answer p {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text);
}
.key-points ul {
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
}
</style>
