<template>
  <div class="debug-panel">
    <h4>🔧 调试视图</h4>

    <div class="debug-section">
      <div class="debug-label">Session ID</div>
      <code class="debug-value">{{ sessionId || '（未创建）' }}</code>
    </div>

    <div class="debug-section" v-if="triggeredAgents?.length">
      <div class="debug-label">最近触发的 Agent 链路</div>
      <div class="agent-chain">
        <span v-for="(agent, i) in triggeredAgents" :key="i" class="agent-tag">
          {{ agent }}
          <span v-if="i < triggeredAgents.length - 1" class="arrow">→</span>
        </span>
      </div>
    </div>

    <div class="debug-section">
      <div class="debug-label-row">
        <span>resume_content_json</span>
        <button v-if="resumeContent" class="copy-btn" @click="copyJson(resumeContent)">
          📋 复制
        </button>
      </div>
      <pre v-if="resumeContent" class="json-block">{{ formatJson(resumeContent) }}</pre>
      <code v-else class="debug-value">null</code>
    </div>

    <div class="debug-section">
      <div class="debug-label-row">
        <span>render_config</span>
        <button v-if="renderConfig" class="copy-btn" @click="copyJson(renderConfig)">
          📋 复制
        </button>
      </div>
      <pre v-if="renderConfig" class="json-block">{{ formatJson(renderConfig) }}</pre>
      <code v-else class="debug-value">null</code>
    </div>
  </div>
</template>

<script setup>
defineProps({
  sessionId: String,
  resumeContent: Object,
  renderConfig: Object,
  triggeredAgents: Array,
})

function formatJson(obj) {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

function copyJson(obj) {
  navigator.clipboard.writeText(JSON.stringify(obj, null, 2))
}
</script>

<style scoped>
.debug-panel {
  max-width: 800px;
}

h4 {
  margin-bottom: 16px;
}

.debug-section {
  margin-bottom: 16px;
}
.debug-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.debug-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.debug-value {
  font-size: 13px;
  color: var(--text);
  background: var(--bg);
  padding: 6px 10px;
  border-radius: 4px;
  display: block;
}

.agent-chain {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.agent-tag {
  font-size: 12px;
  background: #eef2ff;
  color: var(--primary);
  padding: 4px 10px;
  border-radius: 4px;
}
.arrow {
  color: var(--text-light);
  margin-left: 6px;
}

.json-block {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 14px;
  border-radius: var(--radius);
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.copy-btn {
  font-size: 12px;
  background: var(--bg);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--text-secondary);
  transition: all var(--transition);
}
.copy-btn:hover {
  background: var(--border);
}
</style>
