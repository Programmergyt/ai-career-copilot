<template>
  <div class="job-analysis">
    <div v-if="!job" class="empty-state">
      <div class="empty-icon">📋</div>
      <p>尚未解析岗位信息</p>
      <p class="hint">在左侧对话框中粘贴 JD 或上传 JD 文件</p>
    </div>

    <template v-else>
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
        <h4>🛠️ 技术栈</h4>
        <div class="tag-list">
          <span v-for="t in job.tech_stack" :key="t" class="tag tech">{{ t }}</span>
        </div>
      </section>

      <!-- 硬技能 -->
      <section class="card" v-if="job.hard_skills?.length">
        <h4>💡 硬技能</h4>
        <div class="tag-list">
          <span v-for="s in job.hard_skills" :key="s" class="tag skill">{{ s }}</span>
        </div>
      </section>

      <!-- 软技能 -->
      <section class="card" v-if="job.soft_skills?.length">
        <h4>🤝 软技能</h4>
        <div class="tag-list">
          <span v-for="s in job.soft_skills" :key="s" class="tag soft">{{ s }}</span>
        </div>
      </section>

      <!-- 职责 -->
      <section class="card" v-if="job.responsibilities?.length">
        <h4>📌 职责</h4>
        <ul class="list">
          <li v-for="(r, i) in job.responsibilities" :key="i">{{ r }}</li>
        </ul>
      </section>

      <!-- 关键词 -->
      <section class="card" v-if="job.keywords?.length">
        <h4>🔑 核心关键词</h4>
        <div class="tag-list">
          <span v-for="k in job.keywords" :key="k" class="tag keyword">{{ k }}</span>
        </div>
      </section>

      <!-- 加分项 -->
      <section class="card" v-if="job.bonus_items?.length">
        <h4>⭐ 加分项</h4>
        <ul class="list">
          <li v-for="(b, i) in job.bonus_items" :key="i">{{ b }}</li>
        </ul>
      </section>

      <!-- Gap 分析 -->
      <section class="card" v-if="gaps?.length">
        <h4>📊 Gap 分析</h4>
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
          <p v-if="gap.suggestion" class="gap-suggestion">💡 {{ gap.suggestion }}</p>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
defineProps({
  job: Object,
  gaps: Array,
})
</script>

<style scoped>
.job-analysis {
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

.card {
  background: var(--bg);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
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
  border-radius: 4px;
  font-size: 12px;
}
.tag.tech { background: #dbeafe; color: #1d4ed8; }
.tag.skill { background: #dcfce7; color: #166534; }
.tag.soft { background: #fef3c7; color: #92400e; }
.tag.keyword { background: #ede9fe; color: #5b21b6; }

.list {
  padding-left: 20px;
  font-size: 13px;
  line-height: 1.8;
}

.gap-item {
  padding: 10px;
  background: var(--bg-white);
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
  border-radius: 4px;
}
.gap-level.high, .gap-level.critical { background: #fef2f2; color: var(--danger); }
.gap-level.medium { background: #fffbeb; color: var(--warning); }
.gap-level.low { background: #f0fdf4; color: var(--success); }
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
