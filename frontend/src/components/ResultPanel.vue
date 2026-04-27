<template>
  <div class="result-panel">
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
        <span v-if="tab.badge" class="tab-badge">{{ tab.badge }}</span>
      </button>
    </div>

    <div class="tab-content">
      <!-- 项目介绍 -->
      <ProjectIntro v-if="activeTab === 'intro'" />

      <!-- 岗位分析 -->
      <JobAnalysis v-if="activeTab === 'job'" :job="job" :gaps="gaps" :session-id="sessionId" />

      <!-- 简历预览 -->
      <ResumePreview
        v-if="activeTab === 'resume'"
        :resume-html="resumeHtml"
        :session-id="sessionId"
      />

      <!-- 缺失信息 -->
      <GapsPanel v-if="activeTab === 'gaps'" :gaps="gaps" :questions="questions" :session-id="sessionId" />

      <!-- 面试问答 -->
      <InterviewPanel v-if="activeTab === 'interview'" :interview-qa="interviewQa" :session-id="sessionId" />

      <!-- 调试视图 -->
      <DebugPanel
        v-if="activeTab === 'debug'"
        :session-id="sessionId"
        :resume-content="resumeContent"
        :render-config="renderConfig"
        :triggered-agents="triggeredAgents"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import ProjectIntro from './tabs/ProjectIntro.vue'
import JobAnalysis from './tabs/JobAnalysis.vue'
import ResumePreview from './tabs/ResumePreview.vue'
import GapsPanel from './tabs/GapsPanel.vue'
import InterviewPanel from './tabs/InterviewPanel.vue'
import DebugPanel from './tabs/DebugPanel.vue'

const props = defineProps({
  sessionId: String,
  job: Object,
  gaps: Array,
  questions: Array,
  resumeHtml: Object,
  resumeContent: Object,
  renderConfig: Object,
  interviewQa: Array,
  triggeredAgents: Array,
})

const activeTab = ref('job')

const tabs = computed(() => [
  { key: 'intro', label: '项目介绍', badge: '' },
  { key: 'job', label: '岗位分析', badge: props.job ? '' : '' },
  { key: 'resume', label: '简历预览', badge: '' },
  {
    key: 'gaps',
    label: '缺失信息',
    badge: props.questions?.length || '',
  },
  { key: 'interview', label: '面试问答', badge: '' },
  { key: 'debug', label: '调试', badge: '' },
])
</script>

<style scoped>
.result-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-white);
}

.tab-bar {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border);
  padding: 10px 12px;
  flex-shrink: 0;
  overflow-x: auto;
  background: rgba(255, 255, 255, 0.96);
}
.tab-btn {
  padding: 8px 13px;
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
  transition:
    background var(--transition),
    color var(--transition),
    box-shadow var(--transition);
  position: relative;
}
.tab-btn:hover {
  color: var(--primary);
  background: var(--primary-subtle);
}
.tab-btn.active {
  color: var(--primary);
  background: var(--primary-soft);
  font-weight: 500;
  box-shadow: inset 0 0 0 1px rgba(26, 115, 232, 0.12);
}
.tab-badge {
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 10px;
  margin-left: 4px;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  background: var(--surface);
}
</style>
