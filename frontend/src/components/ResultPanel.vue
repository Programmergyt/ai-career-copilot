<template>
  <div class="result-panel">
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.icon }} {{ tab.label }}
        <span v-if="tab.badge" class="tab-badge">{{ tab.badge }}</span>
      </button>
    </div>

    <div class="tab-content">
      <!-- 项目介绍 -->
      <ProjectIntro v-if="activeTab === 'intro'" />

      <!-- 岗位分析 -->
      <JobAnalysis v-if="activeTab === 'job'" :job="job" :gaps="gaps" />

      <!-- 简历预览 -->
      <ResumePreview
        v-if="activeTab === 'resume'"
        :resume-html="resumeHtml"
        :session-id="sessionId"
      />

      <!-- 缺失信息 -->
      <GapsPanel v-if="activeTab === 'gaps'" :gaps="gaps" :questions="questions" />

      <!-- 面试问答 -->
      <InterviewPanel v-if="activeTab === 'interview'" :interview-qa="interviewQa" />

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
  { key: 'intro', label: '项目介绍', icon: '✨', badge: '' },
  { key: 'job', label: '岗位分析', icon: '📋', badge: props.job ? '' : '' },
  { key: 'resume', label: '简历预览', icon: '📄', badge: '' },
  {
    key: 'gaps',
    label: '缺失信息',
    icon: '❓',
    badge: props.questions?.length || '',
  },
  { key: 'interview', label: '面试问答', icon: '🎤', badge: '' },
  { key: 'debug', label: '调试', icon: '🔧', badge: '' },
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
  border-bottom: 1px solid var(--border);
  padding: 0 12px;
  flex-shrink: 0;
  overflow-x: auto;
}
.tab-btn {
  padding: 12px 16px;
  background: none;
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
  border-bottom: 2px solid transparent;
  transition: all var(--transition);
  position: relative;
}
.tab-btn:hover {
  color: var(--text);
}
.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
  font-weight: 500;
}
.tab-badge {
  background: var(--danger);
  color: #fff;
  font-size: 11px;
  padding: 0 6px;
  border-radius: 10px;
  margin-left: 4px;
}

.tab-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
</style>
