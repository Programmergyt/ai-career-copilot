"""匹配度计算工具 — 计算个人技能与 JD 要求的匹配度"""


def compute_match_score(
    jd_skills: list[str],
    personal_skills: list[str],
) -> dict:
    """计算 JD 要求技能与个人技能的匹配情况。

    Args:
        jd_skills: JD 中提取的技能/关键词列表
        personal_skills: 个人拥有的技能/关键词列表

    Returns:
        {
            "score": float (0-1),
            "matched": [...],
            "missing": [...],
        }
    """
    jd_set = {s.lower().strip() for s in jd_skills}
    personal_set = {s.lower().strip() for s in personal_skills}

    matched = sorted(jd_set & personal_set)
    missing = sorted(jd_set - personal_set)

    score = len(matched) / len(jd_set) if jd_set else 0.0

    return {
        "score": round(score, 2),
        "matched": matched,
        "missing": missing,
    }
