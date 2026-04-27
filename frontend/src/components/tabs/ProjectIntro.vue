<template>
  <section class="project-intro">
    <header class="hero-card">
      <p class="eyebrow">AI Career Copilot</p>
      <h2>面向求职场景的多智能体简历与面试辅助工具</h2>
      <p class="lead">
        这个项目将 JD 分析、候选人信息提取、简历生成、缺失项追问和模拟面试整合到同一轮会话中。
        你可以像和助手聊天一样，逐步补齐材料并持续修改结果。
      </p>
      <div class="hero-links">
        <a href="http://8.153.79.69:3001" target="_blank" rel="noreferrer">在线体验</a>
        <a href="https://github.com/Programmergyt/ai-career-copilot" target="_blank" rel="noreferrer">GitHub 仓库</a>
      </div>
    </header>

    <div class="grid">
      <article class="info-card">
        <h3>推荐使用流程</h3>
        <ol>
          <li>第一次对话先粘贴或上传目标 JD，让系统建立岗位上下文。</li>
          <li>后续继续上传个人基本信息、实习经历、项目经历或已有简历材料。</li>
          <li>如果信息不完整，可以直接要求系统补充缺失项、追问细节或重写某一段内容。</li>
          <li>生成结果后，可以继续下达修改指令，例如强化某项经历、调整语气或突出匹配点。</li>
        </ol>
      </article>

      <article class="info-card">
        <h3>当前支持的附件格式</h3>
        <ul>
          <li>PDF `.pdf`</li>
          <li>Word `.docx`</li>
          <li>Plain Text `.txt`</li>
          <li>Markdown `.md`</li>
        </ul>
        <p class="tip">建议优先上传原始 JD、项目说明、实习记录和个人简历，以获得更稳定的结构化抽取结果。</p>
      </article>

      <article class="info-card wide">
        <h3>适合怎么用</h3>
        <p>
          如果你正在准备投递，可以先上传 JD，再把零散的候选人材料分批发给系统。它会在当前会话里持续记住上下文，并把岗位分析、简历预览、缺失信息和面试问答同步更新到右侧结果面板中。
        </p>
        <p>
          如果你是开发者，也可以直接查看开源代码，复用这个多智能体工作流作为简历优化、职业助手或求职辅导产品的基础框架。
        </p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.project-intro {
  display: flex;
  flex-direction: column;
  gap: 16px;
  color: var(--text);
  animation: panelFadeIn 0.24s ease both;
}

.hero-card,
.info-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  transition:
    border-color var(--transition),
    box-shadow var(--transition),
    transform var(--transition);
}

.hero-card:hover,
.info-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
  transform: translateY(-1px);
}

.hero-card {
  padding: 24px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--primary);
}

.hero-card h2 {
  margin: 0;
  font-size: 26px;
  line-height: 1.3;
}

.lead {
  margin: 12px 0 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-secondary);
}

.hero-links {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 18px;
}

.hero-links a {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 0 16px;
  border-radius: 999px;
  text-decoration: none;
  font-weight: 600;
  border: 1px solid transparent;
  transition:
    background var(--transition),
    border-color var(--transition),
    transform var(--transition),
    box-shadow var(--transition);
}

.hero-links a:first-child {
  background: var(--primary);
  color: #fff;
}

.hero-links a:last-child {
  background: #fff;
  border-color: var(--border);
  color: var(--primary);
}

.hero-links a:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(26, 115, 232, 0.16);
}

.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.info-card {
  padding: 20px;
}

.info-card h3 {
  margin: 0 0 12px;
  font-size: 18px;
}

.info-card p,
.info-card li {
  color: var(--text-secondary);
  line-height: 1.8;
}

.info-card ol,
.info-card ul {
  margin: 0;
  padding-left: 20px;
}

.tip {
  margin: 12px 0 0;
  font-size: 13px;
}

.wide {
  grid-column: 1 / -1;
}

@media (max-width: 900px) {
  .grid {
    grid-template-columns: 1fr;
  }

  .wide {
    grid-column: auto;
  }

  .hero-card h2 {
    font-size: 24px;
  }
}
</style>
