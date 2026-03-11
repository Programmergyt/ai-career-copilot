"""test_memory.py — 长期记忆模块测试"""

import os
from memory.long_term_memory import (
    init_db,
    save_jd,
    save_resume,
    get_preference,
    set_preference,
)


class TestLongTermMemory:
    """测试 SQLite 长期记忆。"""

    def test_init_and_save_jd(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)

        jd_id = save_jd("测试 JD 文本", {"tech_stack": ["Python"]}, db)
        assert isinstance(jd_id, int)
        assert jd_id >= 1

    def test_save_resume(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)

        jd_id = save_jd("JD", {}, db)
        resume_id = save_resume(jd_id, "# 简历内容", {"pass": True}, db)
        assert isinstance(resume_id, int)

    def test_preferences(self, tmp_path):
        db = str(tmp_path / "test.db")
        init_db(db)

        assert get_preference("style", default="简洁", db_path=db) == "简洁"

        set_preference("style", "详细", db)
        assert get_preference("style", db_path=db) == "详细"

        # 覆盖
        set_preference("style", "学术", db)
        assert get_preference("style", db_path=db) == "学术"
