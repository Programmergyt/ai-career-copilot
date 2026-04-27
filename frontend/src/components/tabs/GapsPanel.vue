<template>
  <div class="gaps-panel">
    <div v-if="!questions?.length && !gaps?.length" class="empty-state">
      <div class="empty-mark" aria-hidden="true"></div>
      <p>暂无缺失信息</p>
      <p class="hint">系统会在分析后列出需要补充的信息</p>
    </div>

    <div v-else class="toolbar">
      <button class="toolbar-btn" @click="download('txt')">导出 TXT</button>
      <button class="toolbar-btn" @click="download('json')">导出 JSON</button>
      <button class="toolbar-btn" @click="download('md')">导出 MD</button>
    </div>

    <!-- 待追问问题 -->
    <section v-if="questions?.length">
      <h4>待补充信息（{{ questions.length }} 项）</h4>
      <div
        v-for="(q, i) in questions"
        :key="q.id || i"
        class="question-card"
      >
        <div class="question-header">
          <span class="question-index">#{{ i + 1 }}</span>
          <span v-if="q.category" class="question-category">{{ q.category }}</span>
          <span v-if="q.priority" class="question-priority" :class="q.priority">
            {{ q.priority }}
          </span>
        </div>
        <p class="question-text">{{ q.question || q.content || q.text }}</p>
        <p v-if="q.reason" class="question-reason">原因：{{ q.reason }}</p>
      </div>
    </section>

    <!-- Gap 列表 -->
    <section v-if="gaps?.length" style="margin-top: 20px;">
      <h4>能力缺口（{{ gaps.length }} 项）</h4>
      <div
        v-for="(gap, i) in gaps"
        :key="gap.id || i"
        class="gap-card"
      >
        <div class="gap-row">
          <span class="gap-name">{{ gap.skill || gap.area || gap.name }}</span>
          <span class="gap-severity" :class="gap.severity || gap.level || 'info'">
            {{ gap.severity || gap.level || 'info' }}
          </span>
        </div>
        <p v-if="gap.description" class="gap-desc">{{ gap.description }}</p>
        <p v-if="gap.suggestion" class="gap-tip">{{ gap.suggestion }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { exportArtifact, readApiError } from '../../api/index.js'

const props = defineProps({
  gaps: Array,
  questions: Array,
  sessionId: String,
})

async function download(format) {
  if (!props.sessionId || (!props.gaps?.length && !props.questions?.length)) return
  try {
    const { data } = await exportArtifact(props.sessionId, 'gaps', format)
    downloadBlob(data, `gaps.${format === 'md' ? 'md' : format}`, format)
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
</script>

<style scoped>
.gaps-panel {
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
.empty-mark::after {
  content: '';
  position: absolute;
  left: 14px;
  top: 11px;
  width: 12px;
  height: 18px;
  border-right: 2px solid var(--primary);
  border-bottom: 2px solid var(--primary);
  transform: rotate(42deg);
}
.hint {
  font-size: 13px;
  color: var(--text-light);
  margin-top: 6px;
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
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

h4 {
  font-size: 15px;
  margin-bottom: 12px;
}

.question-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: var(--shadow);
  transition:
    border-color var(--transition),
    box-shadow var(--transition),
    transform var(--transition);
}
.question-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}
.question-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.question-index {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
}
.question-category {
  font-size: 11px;
  background: var(--primary-soft);
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 999px;
}
.question-priority {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}
.question-priority.high { background: #fce8e6; color: var(--danger); }
.question-priority.medium { background: #fff4d8; color: var(--warning); }
.question-priority.low { background: #e6f4ea; color: var(--success); }
.question-text {
  font-size: 14px;
  line-height: 1.6;
}
.question-reason {
  font-size: 12px;
  color: var(--text-light);
  margin-top: 4px;
}

.gap-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
  margin-bottom: 8px;
  box-shadow: var(--shadow);
  transition:
    border-color var(--transition),
    box-shadow var(--transition),
    transform var(--transition);
}
.gap-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}
.gap-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.gap-name {
  font-weight: 500;
}
.gap-severity {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}
.gap-severity.high, .gap-severity.critical { background: #fce8e6; color: var(--danger); }
.gap-severity.medium { background: #fff4d8; color: var(--warning); }
.gap-severity.low, .gap-severity.info { background: #e6f4ea; color: var(--success); }
.gap-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 6px;
}
.gap-tip {
  font-size: 12px;
  color: var(--primary);
  margin-top: 4px;
}
</style>
