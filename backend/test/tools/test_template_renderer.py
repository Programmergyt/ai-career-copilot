# 示例: 在项目根目录执行 pytest backend/test/tools/test_template_renderer.py -sv
"""template_renderer 模块单元测试。"""

import pytest

from tools.template_renderer import render_resume_html, _build_template_variables
from workflow.state import (
    ResumeContent, ResumeProfile, ResumeContentMeta,
    SectionItem, Education, RenderConfig, PageMargin,
)


@pytest.fixture
def sample_resume_content() -> ResumeContent:
    """基于 fixtures/profiles/虚拟候选人信息.md 构造的简历内容。"""
    return ResumeContent(
        profile=ResumeProfile(
            name="林知遥",
            email="lin.zhiyou@example.test",
            phone="+86-13900001234",
            city="杭州",
            github="https://github.com/linzhiyou-demo",
            education=[
                Education(
                    id="edu_1",
                    school="星海理工大学",
                    major="控制工程",
                    degree="硕士",
                    start_date="2025-09",
                    end_date="2028-06",
                ),
                Education(
                    id="edu_2",
                    school="星海理工大学",
                    major="人工智能",
                    degree="本科",
                    start_date="2021-09",
                    end_date="2025-06",
                ),
            ],
        ),
        summary="AI 方向研究生，具备 LLM 应用开发和 RAG 系统建设经验。",
        skills=[
            SectionItem(id="sk1", title="Python", content="熟练使用 NumPy / Pandas 进行数据清洗与分析"),
            SectionItem(id="sk2", title="LangChain", content="熟练掌握 LangChain + RAG 开发"),
        ],
        internships=[
            SectionItem(
                id="int1",
                title="远望工业智能 — RAG 诊断平台",
                content="基于 RAG 的 LLM 工作流，实现工业设备故障诊断。",
            ),
        ],
        projects=[
            SectionItem(
                id="prj1",
                title="AI Career Copilot",
                content="基于 LangGraph 多 Agent 协作的智能求职辅助系统。",
            ),
        ],
        awards=[
            SectionItem(id="aw1", title="启明星创新奖学金", content="获得校级创新奖学金与项目实践奖励"),
        ],
        meta=ResumeContentMeta(target_role="AIGC工程师", version=1),
    )


@pytest.fixture
def default_render_config() -> RenderConfig:
    return RenderConfig()


class TestRenderResumeHTML:

    def test_render_produces_html(self, sample_resume_content, default_render_config):
        html = render_resume_html(sample_resume_content, default_render_config)
        assert isinstance(html, str)
        assert len(html) > 0
        assert "<html" in html.lower()

    def test_html_contains_name(self, sample_resume_content, default_render_config):
        html = render_resume_html(sample_resume_content, default_render_config)
        assert "林知遥" in html

    def test_html_contains_sections(self, sample_resume_content, default_render_config):
        html = render_resume_html(sample_resume_content, default_render_config)
        assert "Python" in html
        assert "RAG" in html
        assert "AI Career Copilot" in html

    def test_html_contains_education(self, sample_resume_content, default_render_config):
        html = render_resume_html(sample_resume_content, default_render_config)
        assert "星海理工大学" in html
        assert "控制工程" in html

    def test_html_contains_awards(self, sample_resume_content, default_render_config):
        html = render_resume_html(sample_resume_content, default_render_config)
        assert "启明星创新奖学金" in html


class TestBuildTemplateVariables:

    def test_variables_contain_required_keys(self, sample_resume_content, default_render_config):
        variables = _build_template_variables(sample_resume_content, default_render_config)
        assert "CSS_VARIABLES" in variables
        assert "LAYOUT_CLASS" in variables
        assert "SECTIONS_HTML" in variables
        assert "NAME" in variables
        assert "TARGET_ROLE" in variables

    def test_name_in_variables(self, sample_resume_content, default_render_config):
        variables = _build_template_variables(sample_resume_content, default_render_config)
        assert variables["NAME"] == "林知遥"
        assert variables["TARGET_ROLE"] == "AIGC工程师"

    def test_layout_class_single_column(self, sample_resume_content, default_render_config):
        variables = _build_template_variables(sample_resume_content, default_render_config)
        assert variables["LAYOUT_CLASS"] == "single-column"

    def test_layout_class_double_column(self, sample_resume_content):
        config = RenderConfig(layout_mode="double-column")
        variables = _build_template_variables(sample_resume_content, config)
        assert variables["LAYOUT_CLASS"] == "double-column"


class TestRenderConfigEffects:

    def test_dense_mode(self, sample_resume_content):
        config = RenderConfig(dense_mode=True)
        html = render_resume_html(sample_resume_content, config)
        assert isinstance(html, str)
        assert len(html) > 0

    def test_visibility_map_hides_section(self, sample_resume_content):
        config = RenderConfig(visibility_map={"awards": False})
        html = render_resume_html(sample_resume_content, config)
        assert "启明星创新奖学金" not in html

    def test_custom_section_order(self, sample_resume_content):
        config = RenderConfig(
            section_order=["profile", "projects", "skills", "internships"],
        )
        html = render_resume_html(sample_resume_content, config)
        # 项目经历应该存在于 HTML 中
        assert "AI Career Copilot" in html
