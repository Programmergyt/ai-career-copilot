<template>
  <div class="job-analysis">
    <div v-if="!job" class="empty-state">
      <div class="empty-mark" aria-hidden="true"></div>
      <p>尚未解析岗位信息</p>
      <p class="hint">在左侧对话框中粘贴 JD 或上传 JD 文件</p>
    </div>

    <template v-else>
      <div class="toolbar">
        <button class="toolbar-btn" @click="download('txt')">导出 TXT</button>
        <button class="toolbar-btn" @click="download('json')">导出 JSON</button>
        <button class="toolbar-btn" @click="download('md')">导出 MD</button>
      </div>

      <!-- 基本信息 -->
      <section class="card">
        <h3>{{ job.title || '岗位名称' }}</h3>
        <div class="meta-row" v-if="job.industry">
          <span class="label">行业：</span>{{ job.industry }}
        </div>
        <div class="meta-row" v-if="job.education_requirement">
          <span class="label">学历要求：</span>{{ job.education_requirement }}
        </div>
        <div class="meta-row" v-if="job.experience_requirement">
          <span class="label">经验要求：</span>{{ job.experience_requirement }}
        </div>
      </section>

      <!-- 技术栈 -->
      <section class="card" v-if="job.tech_stack?.length">
        <h4>技术栈</h4>
        <div class="tag-list">
          <span v-for="t in job.tech_stack" :key="t" class="tag tech">{{ t }}</span>
        </div>
      </section>

      <!-- 硬技能 -->
      <section class="card" v-if="job.hard_skills?.length">
        <h4>硬技能</h4>
        <div class="tag-list">
          <span v-for="s in job.hard_skills" :key="s" class="tag skill">{{ s }}</span>
        </div>
      </section>

      <!-- 软技能 -->
      <section class="card" v-if="job.soft_skills?.length">
        <h4>软技能</h4>
        <div class="tag-list">
          <span v-for="s in job.soft_skills" :key="s" class="tag soft">{{ s }}</span>
        </div>
      </section>

      <!-- 职责 -->
      <section class="card" v-if="job.responsibilities?.length">
        <h4>职责</h4>
        <ul class="list">
          <li v-for="(r, i) in job.responsibilities" :key="i">{{ r }}</li>
        </ul>
      </section>

      <!-- 关键词 -->
      <section class="card" v-if="job.keywords?.length">
        <h4>核心关键词</h4>
        <div class="tag-list">
          <span v-for="k in job.keywords" :key="k" class="tag keyword">{{ k }}</span>
        </div>
      </section>

      <!-- 加分项 -->
      <section class="card" v-if="job.bonus_items?.length">
        <h4>加分项</h4>
        <ul class="list">
          <li v-for="(b, i) in job.bonus_items" :key="i">{{ b }}</li>
        </ul>
      </section>

      <!-- Gap 分析 -->
      <section class="card" v-if="gaps?.length">
        <h4>Gap 分析</h4>
        <div v-for="gap in gaps" :key="gap.id || gap.skill" class="gap-item">
          <div class="gap-header">
            <span class="gap-skill">{{ gap.skill || gap.area }}</span>
            <span
              class="gap-level"
              :class="gap.severity || gap.level"
            >
              {{ gap.severity || gap.level || 'info' }}
            </span>
          </div>
          <p v-if="gap.description" class="gap-desc">{{ gap.description }}</p>
          <p v-if="gap.suggestion" class="gap-suggestion">{{ gap.suggestion }}</p>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { exportArtifact, readApiError } from '../../api/index.js'

const props = defineProps({
  job: Object,
  gaps: Array,
  sessionId: String,
})

async function download(format) {
  if (!props.sessionId || !props.job) return
  try {
    const { data } = await exportArtifact(props.sessionId, 'job', format)
    downloadBlob(data, `job-analysis.${format === 'md' ? 'md' : format}`, format)
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
.job-analysis {
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
  inset: 12px;
  border-radius: 8px;
  border: 2px solid var(--primary);
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

.card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: var(--shadow);
  transition:
    border-color var(--transition),
    box-shadow var(--transition),
    transform var(--transition);
}
.card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}
.card h3 {
  font-size: 18px;
  margin-bottom: 8px;
}
.card h4 {
  font-size: 14px;
  margin-bottom: 10px;
  color: var(--text);
}
.meta-row {
  font-size: 13px;
  margin: 4px 0;
  color: var(--text-secondary);
}
.meta-row .label {
  color: var(--text);
  font-weight: 500;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
}
.tag.tech,
.tag.skill,
.tag.soft,
.tag.keyword {
  background: var(--primary-soft);
  color: var(--primary);
}

.list {
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.8;
}

.gap-item {
  padding: 10px;
  background: var(--surface);
  border-radius: 6px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
}
.gap-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.gap-skill {
  font-weight: 500;
}
.gap-level {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}
.gap-level.high, .gap-level.critical { background: #fce8e6; color: var(--danger); }
.gap-level.medium { background: #fff4d8; color: var(--warning); }
.gap-level.low { background: #e6f4ea; color: var(--success); }
.gap-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 6px;
}
.gap-suggestion {
  font-size: 12px;
  color: var(--primary);
  margin-top: 4px;
}
</style>
