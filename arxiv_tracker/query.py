# arxiv_tracker/query.py
import re
from typing import List

FIELDS = ("ti", "abs", "co")  # 标题/摘要/评论（会议常在 comments）

def _quote(term: str) -> str:
    # 有空格或连字符时加引号，避免被拆词
    t = term.strip()
    if re.search(r'[\s-]', t):
        return f'"{t}"'
    return t

def _field_or(fields: List[str], term: str) -> str:
    q = _quote(term)
    return "(" + " OR ".join(f"{f}:{q}" for f in fields) + ")"

def _expand_variants(kw: str) -> List[str]:
    """为一个关键词生成若干变体：连字符/空格、大小写不敏感"""
    k = kw.strip()
    out = {k}
    if " " in k:
        out.add(k.replace(" ", "-"))
    if "-" in k:
        out.add(k.replace("-", " "))
    return sorted(out, key=len, reverse=True)  # 优先长短语

def _kw_group(kw: str) -> str:
    """
    为一个逻辑关键词构造一个子查询：
    - 先尝试短语精确（含连字符/空格变体）
    - 若包含 'open vocabulary' 与 'segmentation'，再加一个“拆词 AND”备选
    """
    variants = _expand_variants(kw)
    parts = []

    # 1) 短语匹配（多个变体，ti/abs/co）
    for v in variants:
        parts.append(_field_or(FIELDS, v))

    # 2) 针对 open-vocabulary segmentation 的拆词 AND（覆盖更多写法）
    low = kw.lower()
    if ("open vocabulary" in low or "open-vocabulary" in low) and "segmentation" in low:
        ov_terms = ["open vocabulary", "open-vocabulary", "open-vocabulary segmentation", "open vocabulary segmentation"]
        seg_terms = ["segmentation", "image segmentation"]
        ov_or = "(" + " OR ".join(_field_or(FIELDS, t) for t in ov_terms) + ")"
        seg_or = "(" + " OR ".join(_field_or(FIELDS, t) for t in seg_terms) + ")"
        parts.append(f"({ov_or} AND {seg_or})")

    return "(" + " OR ".join(parts) + ")"

def build_search_query(categories: List[str], keywords: List[str], logic: str = "AND", exclude_keywords: List[str] = None) -> str:
    """
    生成 arXiv API 的 search_query 字符串。
    - categories: ["cs.CV","cs.LG"] -> (cat:cs.CV OR cat:cs.LG)
    - keywords:   每个 kw 变成一个 _kw_group，关键词之间用 OR 连接
    - exclude_keywords: 排除的关键词列表，使用 ANDNOT 排除
    - 组间逻辑：cat_group (AND/OR) kw_group
    """
    cats = [c.strip() for c in (categories or []) if c and c.strip()]
    keys = [k.strip() for k in (keywords or []) if k and k.strip()]
    exclude_keys = [k.strip() for k in (exclude_keywords or []) if k and k.strip()]
    
    cat_q = ""
    key_q = ""
    exclude_q = ""

    if cats:
        cat_q = "(" + " OR ".join(f"cat:{c}" for c in cats) + ")"
    if keys:
        key_q = "(" + " OR ".join(_kw_group(k) for k in keys) + ")"
    if exclude_keys:
        # 排除关键词：使用 ANDNOT，排除关键词之间用 OR 连接
        exclude_q = "(" + " OR ".join(_kw_group(k) for k in exclude_keys) + ")"

    # 构建查询
    main_query = ""
    if cat_q and key_q:
        op = "AND" if (logic or "AND").upper() == "AND" else "OR"
        main_query = f"{cat_q} {op} {key_q}"
    elif cat_q:
        main_query = cat_q
    elif key_q:
        main_query = key_q
    else:
        # 没给任何条件就回到全站（不建议）
        main_query = "all:*"
    
    # 如果有排除关键词，添加 ANDNOT
    if exclude_q:
        return f"({main_query}) ANDNOT {exclude_q}"
    else:
        return main_query
