<template>
  <div class="gaps-panel">
    <div v-if="!questions?.length && !gaps?.length" class="empty-state">
      <div class="empty-icon">✅</div>
      <p>暂无缺失信息</p>
      <p class="hint">系统会在分析后列出需要补充的信息</p>
    </div>

    <!-- 待追问问题 -->
    <section v-if="questions?.length">
      <h4>❓ 待补充信息（{{ questions.length }} 项）</h4>
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
      <h4>📊 能力缺口（{{ gaps.length }} 项）</h4>
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
        <p v-if="gap.suggestion" class="gap-tip">💡 {{ gap.suggestion }}</p>
      </div>
    </section>
  </div>
</template>

<script setup>
defineProps({
  gaps: Array,
  questions: Array,
})
</script>

<style scoped>
.gaps-panel {
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

h4 {
  font-size: 15px;
  margin-bottom: 12px;
}

.question-card {
  background: var(--bg);
  border-radius: var(--radius);
  padding: 14px;
  margin-bottom: 10px;
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
  background: #eef2ff;
  color: var(--primary);
  padding: 2px 8px;
  border-radius: 4px;
}
.question-priority {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}
.question-priority.high { background: #fef2f2; color: var(--danger); }
.question-priority.medium { background: #fffbeb; color: var(--warning); }
.question-priority.low { background: #f0fdf4; color: var(--success); }
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
  background: var(--bg);
  border-radius: var(--radius);
  padding: 12px;
  margin-bottom: 8px;
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
  border-radius: 4px;
}
.gap-severity.high, .gap-severity.critical { background: #fef2f2; color: var(--danger); }
.gap-severity.medium { background: #fffbeb; color: var(--warning); }
.gap-severity.low, .gap-severity.info { background: #f0fdf4; color: var(--success); }
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
