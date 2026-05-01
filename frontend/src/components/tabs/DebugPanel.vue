<template>
  <div class="debug-panel">
    <h4>调试视图</h4>

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
      <div class="debug-label">上下文窗口</div>
      <div class="metrics-grid">
        <div class="metric-item">
          <span>预算</span>
          <strong>{{ formatNumber(contextWindow?.budget_tokens) }}</strong>
        </div>
        <div class="metric-item">
          <span>Graph 前估算</span>
          <strong>{{ formatNumber(contextWindow?.estimated_tokens_after) }}</strong>
        </div>
        <div class="metric-item">
          <span>记忆长度</span>
          <strong>{{ formatNumber(contextWindow?.memory_tokens_after) }}</strong>
        </div>
        <div class="metric-item">
          <span>裁剪长度</span>
          <strong>{{ formatNumber(contextWindow?.truncated_tokens) }}</strong>
        </div>
      </div>
      <div class="debug-value compact">
        provider={{ contextWindow?.provider || '-' }} /
        model={{ contextWindow?.model || '-' }} /
        within_budget={{ contextWindow?.within_budget ?? true }}
      </div>
    </div>

    <div class="debug-section">
      <div class="debug-label-row">
        <span>LLM Token 调用记录</span>
        <button v-if="llmTokenUsage?.length" class="copy-btn" @click="copyJson(llmTokenUsage)">
          复制
        </button>
      </div>
      <div v-if="llmTokenUsage?.length" class="usage-table-wrap">
        <table class="usage-table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Prompt</th>
              <th>Completion</th>
              <th>Total</th>
              <th>裁剪</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in llmTokenUsage" :key="item.call_id">
              <td>{{ item.agent_name }}</td>
              <td>{{ formatNumber(item.prompt_tokens || item.estimated_prompt_tokens) }}</td>
              <td>{{ formatNumber(item.completion_tokens) }}</td>
              <td>{{ formatNumber(item.total_tokens) }}</td>
              <td>{{ formatNumber(item.prompt_truncated_tokens) }}</td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td>合计</td>
              <td>{{ formatNumber(totalPromptTokens) }}</td>
              <td>{{ formatNumber(totalCompletionTokens) }}</td>
              <td>{{ formatNumber(totalTokens) }}</td>
              <td>{{ formatNumber(totalPromptCroppedTokens) }}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      <code v-else class="debug-value">暂无 LLM 调用记录</code>
    </div>

    <div class="debug-section">
      <div class="debug-label-row">
        <span>resume_content_json</span>
        <button v-if="resumeContent" class="copy-btn" @click="copyJson(resumeContent)">
          复制
        </button>
      </div>
      <pre v-if="resumeContent" class="json-block">{{ formatJson(resumeContent) }}</pre>
      <code v-else class="debug-value">null</code>
    </div>

    <div class="debug-section">
      <div class="debug-label-row">
        <span>render_config</span>
        <button v-if="renderConfig" class="copy-btn" @click="copyJson(renderConfig)">
          复制
        </button>
      </div>
      <pre v-if="renderConfig" class="json-block">{{ formatJson(renderConfig) }}</pre>
      <code v-else class="debug-value">null</code>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  sessionId: String,
  resumeContent: Object,
  renderConfig: Object,
  triggeredAgents: Array,
  llmTokenUsage: Array,
  contextWindow: Object,
})

const totalPromptTokens = computed(() => sumUsage('prompt_tokens', 'estimated_prompt_tokens'))
const totalCompletionTokens = computed(() => sumUsage('completion_tokens'))
const totalTokens = computed(() => sumUsage('total_tokens'))
const totalPromptCroppedTokens = computed(() => sumUsage('prompt_truncated_tokens'))

function sumUsage(primary, fallback) {
  return (props.llmTokenUsage || []).reduce((sum, item) => {
    return sum + Number(item?.[primary] || (fallback ? item?.[fallback] : 0) || 0)
  }, 0)
}

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

function formatNumber(value) {
  const number = Number(value || 0)
  return number.toLocaleString()
}
</script>

<style scoped>
.debug-panel {
  max-width: 800px;
  animation: panelFadeIn 0.24s ease both;
}

h4 {
  margin-bottom: 16px;
}

.debug-section {
  margin-bottom: 16px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #fff;
  box-shadow: var(--shadow);
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
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 6px 10px;
  border-radius: 6px;
  display: block;
}
.debug-value.compact {
  margin-top: 10px;
  white-space: normal;
  word-break: break-word;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.metric-item {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}
.metric-item span {
  display: block;
  margin-bottom: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}
.metric-item strong {
  display: block;
  color: var(--text);
  font-size: 15px;
}

.usage-table-wrap {
  overflow-x: auto;
}
.usage-table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
  font-size: 12px;
}
.usage-table th,
.usage-table td {
  padding: 8px;
  border: 1px solid var(--border);
  text-align: left;
}
.usage-table th {
  background: var(--primary-subtle);
  color: var(--text-secondary);
  font-weight: 600;
}
.usage-table tfoot td {
  font-weight: 700;
  background: var(--surface);
}

.agent-chain {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}
.agent-tag {
  font-size: 12px;
  background: var(--primary-soft);
  color: var(--primary);
  padding: 4px 10px;
  border-radius: 999px;
}
.arrow {
  color: var(--text-light);
  margin-left: 6px;
}

.json-block {
  background: #f7faff;
  color: var(--text);
  border: 1px solid var(--border);
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
  background: #fff;
  border: 1px solid var(--border);
  padding: 3px 10px;
  border-radius: 999px;
  color: var(--primary);
  transition:
    background var(--transition),
    border-color var(--transition),
    transform var(--transition);
}
.copy-btn:hover {
  background: var(--primary-soft);
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

@media (max-width: 700px) {
  .metrics-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
