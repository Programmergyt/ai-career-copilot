<template>
  <div class="interview-panel">
    <div v-if="!interviewQa?.length" class="empty-state">
      <div class="empty-icon">🎤</div>
      <p>面试问答尚未生成</p>
      <p class="hint">完成简历内容生成后，系统将自动生成面试题</p>
    </div>

    <template v-else>
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

defineProps({
  interviewQa: Array,
})

const expandedSet = reactive(new Set())

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

.qa-count {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.qa-card {
  background: var(--bg);
  border-radius: var(--radius);
  margin-bottom: 10px;
  overflow: hidden;
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
  background: #f0f0f0;
}
.qa-index {
  font-weight: 700;
  color: var(--primary);
  font-size: 13px;
  flex-shrink: 0;
}
.qa-type {
  font-size: 11px;
  background: #eef2ff;
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 4px;
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
