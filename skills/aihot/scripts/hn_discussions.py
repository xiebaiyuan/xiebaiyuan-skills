#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 要闻简报的 HN 讨论链接：回填 + 单条查询

问题：简报条目只给了「信源链接」（文章原站），HN 被标成 `HN（221 分）` 却没有
`news.ycombinator.com/item?id=…` 的讨论页链接——点进去只能读文章，读不到讨论。

做法：用 HN Algolia API 按文章 URL 反查 item id（`restrictSearchableAttributes=url`），
取分数最高的那条（同一 URL 常有多次提交，讨论量集中在高分帖），把讨论链接插进
`HN（X 分）` 片段里。结果带缓存，重复跑不重复请求。

用法：
    python hn_discussions.py lookup <url>          # 单条查询，打印候选
    python hn_discussions.py backfill --dry        # 预演：只报统计不改文件
    python hn_discussions.py backfill              # 回填 每日要闻/*.md
    python hn_discussions.py backfill --since 2026-09-01
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

VAULT = os.path.expanduser("~/AI_DOC/调研分析/每日要闻")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(BASE, "data", "hn_lookup.json")
HN_ITEM = "https://news.ycombinator.com/item?id={}"
ALGOLIA = ("http://hn.algolia.com/api/v1/search?query={q}"
           "&restrictSearchableAttributes=url&hitsPerPage=6")
ALGOLIA_TITLE = ("http://hn.algolia.com/api/v1/search?query={q}"
                 "&tags=story&hitsPerPage=8")
CACHE_V = "v4"      # 匹配逻辑改了就把这个版本号 +1，避免复用旧结论（缓存按 key 存）

LIST_ITEM = re.compile(r"^\s*(?:\d+\.|[-*])\s*\[")          # 条目行（带链接的列表项）
MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
HN_FRAG = re.compile(r"HN（([^）]*)）")                        # HN（221 分） / HN（576 分，643 条评论）
HN_BARE = re.compile(r"([—·+]\s*)HN(?![（\w])")                # 无括号的 HN 标记
ALREADY = re.compile(r"news\.ycombinator\.com|\bHN 讨论\b")


def log(*a):
    print(*a, file=sys.stderr)


def load_cache() -> dict:
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(c: dict):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=0)


def norm_url(u: str) -> str:
    u = u.split("?")[0].split("#")[0].rstrip("/")
    return re.sub(r"^https?://(www\.)?", "", u).lower()


def lookup(url: str, cache: dict, refresh: bool = False) -> dict | None:
    """返回 {'id','points','comments','title'}，找不到返回 None。"""
    key = f"url{CACHE_V}::" + norm_url(url)
    if key in cache and not refresh:
        return cache[key]
    q = urllib.parse.quote(norm_url(url))      # 查询串必须是 URL 本身（别把缓存 key 前缀一起发了）
    try:
        with urllib.request.urlopen(ALGOLIA.format(q=q), timeout=25) as r:
            data = json.load(r)
    except Exception as e:
        log(f"[hn] 查询失败 {url[:60]}：{e}")
        return None
    hits = [h for h in (data.get("hits") or []) if norm_url(h.get("url") or "") == norm_url(url)]
    best = None
    if hits:
        # 同 URL 多次提交：取分数最高（讨论集中在高分帖），并列时取评论最多
        best = max(hits, key=lambda h: (h.get("points") or 0, h.get("num_comments") or 0))
        best = {"id": best["objectID"], "points": best.get("points"),
                "comments": best.get("num_comments"), "title": (best.get("title") or "")[:120]}
    cache[key] = best
    time.sleep(0.25)                      # 对公开 API 客气一点
    return best


def recorded_score(frag: str) -> int | None:
    m = re.search(r"([\d,]{1,7})\s*分", frag)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


STOP = {"the", "for", "with", "from", "and", "that", "this", "into", "your", "you", "why", "how",
        "new", "are", "not", "has", "have", "was", "its", "out", "about"}


SLUGWORD = re.compile(r"[A-Za-z]{4,}")


def url_slug_tokens(url: str) -> list[str]:
    """从文章 URL 的路径里取有意义的英文词（HN 帖标题往往就是 URL slug 的展开）。"""
    m = re.match(r"https?://[^/]+/(.*)", url or "")
    path = m.group(1) if m else ""
    words = [w.lower() for w in SLUGWORD.findall(path)]
    skip = {"http", "https", "html", "index", "posts", "blog", "blogs", "news", "articles",
            "article", "story", "stories", "watch", "id", "com", "org", "net", "www"}
    return [w for w in words if w not in skip][:8]


def quoted_titles(block: str) -> list[str]:
    """条目正文里引号包住的英文帖名（如「A misalignment of AI in mathematics」）——最准的查询串。"""
    out = []
    for m in re.finditer(r"[「“\"]([A-Za-z][^」”\"]{10,90})[」”\"]", block or ""):
        t = m.group(1).strip()
        if len(SLUGWORD.findall(t)) >= 2 or len(t) >= 18:
            out.append(t)
    for m in re.finditer(r"\*\*([A-Z][A-Za-z0-9 ,:'\-]{12,80})\*\*", block or ""):
        if len(SLUGWORD.findall(m.group(1))) >= 2:
            out.append(m.group(1).strip())
    seen, uniq = set(), []
    for t in out:
        k = t.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    return uniq[:3]


def days_apart(a: str, b: str) -> int:
    from datetime import date
    try:
        da = date.fromisoformat(a[:10])
        db = date.fromisoformat(b[:10])
        return abs((da - db).days)
    except Exception:
        return 0


def related_thread_lookup(url: str, title: str, want: int, cache: dict,
                          extra_queries: list[str] | None = None,
                          brief_date: str = "") -> dict | None:
    """简报记录的 HN 分数属于「另一个 URL 的帖子」（同题材/官方站）时的兜底：
    用 URL slug 词或条目标题词搜 story，取分数同量级且词重合最多的那条。
    不限制域名（HN 帖常指向别处的同名来源），但要求分数同量级 + 词重合 —— 两头都卡住。"""
    if not want or want < 50:
        return None
    key = (f"related{CACHE_V}::" + re.sub(r"\W+", " ", (url or title))[:60] + f"#{want}#{brief_date}#"
           + re.sub(r"\W+", " ", " ".join(extra_queries or []))[:40])
    if key in cache:
        return cache[key]
    cands_q = list(extra_queries or [])
    slug = url_slug_tokens(url)
    if len(slug) >= 2:
        cands_q.append(" ".join(slug[:5]))
    toks = [w for w in SLUGWORD.findall(title.lower()) if w not in STOP]
    if len(toks) >= 2:
        cands_q.append(" ".join(toks[:4]))
    best = None
    best_key = (0, -1e9)
    for q in cands_q:
        try:
            with urllib.request.urlopen(ALGOLIA_TITLE.format(q=urllib.parse.quote(q)), timeout=25) as r:
                hits = (json.load(r).get("hits") or [])
        except Exception:
            continue
        words = set(q.split())
        # 分数只涨不跌：下界 0.9×（比简报记录还低 = 不是同一条帖），上界放宽到 20×
        for h in hits:
            p = h.get("points") or 0
            if not (want * 0.9 <= p <= want * 20):
                continue
            if brief_date and h.get("created_at") and days_apart(brief_date, h["created_at"]) > 45:
                continue                                   # 同名老帖（如 2018 年那条）

            ht = (h.get("title") or "").lower()
            shared = sum(1 for w in words if w in ht)
            if shared < 2 and (len(words) > 1 and shared / len(words) < 0.5):
                continue
            k = (shared, -abs(p - want))
            if k > best_key:
                best_key = k
                best = h
        time.sleep(0.25)
    out = None
    if best:
        out = {"id": best["objectID"], "points": best.get("points"),
               "comments": best.get("num_comments"), "title": (best.get("title") or "")[:120],
               "url": best.get("url"), "related": True}
    cache[key] = out
    return out


def domain_of(u: str) -> str:
    m = re.match(r"https?://([^/]+)", u or "")
    d = (m.group(1) if m else "").lower()
    return re.sub(r"^www\.", "", d)


def title_lookup(title: str, want: int | None, cache: dict, article_url: str = "") -> dict | None:
    """按标题搜 HN（URL 对不上时的兜底）。三道闸：标题词重合 ≥60%、域名一致、分数同量级。
    任一不过就返回 None —— 宁缺勿错，错链比没链更糟。"""
    key = f"title{CACHE_V}::" + re.sub(r"\W+", " ", title.lower())[:60]
    if key in cache:
        return cache[key]
    toks = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9]{3,}", title.lower()) if w not in STOP][:6]
    if len(toks) < 2:
        cache[key] = None
        return None
    q = urllib.parse.quote(" ".join(toks[:4]))
    try:
        with urllib.request.urlopen(ALGOLIA_TITLE.format(q=q), timeout=25) as r:
            hits = (json.load(r).get("hits") or [])
    except Exception:
        hits = []
    dom = domain_of(article_url)

    def share(h):
        t = (h.get("title") or "").lower()
        return sum(1 for w in toks if w in t) / max(1, len(toks))

    cands = [h for h in hits
             if share(h) >= 0.6
             and (not dom or domain_of(h.get("url") or "") == dom)]
    best = None
    if cands:
        if want:
            cand = min(cands, key=lambda h: abs((h.get("points") or 0) - want))
            p = cand.get("points") or 0
            if want * 0.5 <= p <= want * 2.5:      # 同量级才算
                best = cand
        else:
            best = max(cands, key=lambda h: (h.get("points") or 0))
        if best:
            best = {"id": best["objectID"], "points": best.get("points"),
                    "comments": best.get("num_comments"), "title": (best.get("title") or "")[:120]}
    cache[key] = best
    time.sleep(0.25)
    return best


def mk_link(h: dict) -> str:
    c = h.get("comments") or 0
    extra = f"，{c} 条评论" if c else ""
    tag = "同题材" if h.get("related") else ""
    return f"[💬 讨论{tag}（{h['points']} 分{extra}）]({HN_ITEM.format(h['id'])})"


def patch_line(ln: str, h: dict) -> str | None:
    """把讨论链接插进这一行的 HN 标记；插不进去返回 None。"""
    if ALREADY.search(ln):
        return None
    link = mk_link(h)
    m = HN_FRAG.search(ln)
    if m:
        inner = m.group(1).strip()
        if "讨论" in inner:
            return None
        return ln[:m.start()] + f"HN（{inner} · {link}）" + ln[m.end():]
    m = HN_BARE.search(ln)
    if m:
        return ln[:m.end()] + f" {link}" + ln[m.end():]
    return None


def iter_items(text: str):
    """产出 (行号, 行内容, 文章 url)"""
    for i, ln in enumerate(text.splitlines()):
        if not LIST_ITEM.match(ln) or "HN" not in ln:
            continue
        m = MD_LINK.search(ln)
        if m:
            yield i, ln, m.group(2)


LINK_INSERTED = re.compile(r"\s*·?\s*\[💬 讨论(?:同题材)?（[^）]*）\]\(https://news\.ycombinator\.com/item\?id=\d+\)")


def reset(since: str | None, dry: bool) -> int:
    """剥掉之前插入的讨论链接（幂等重跑用）。"""
    files = sorted(glob.glob(os.path.join(VAULT, "20*.md")))
    if since:
        files = [f for f in files if os.path.basename(f)[:10] >= since]
    n = 0
    for path in files:
        txt = open(path, encoding="utf-8").read()
        if "news.ycombinator.com" not in txt:
            continue
        new = LINK_INSERTED.sub("", txt)
        new = re.sub(r"（([^）\n]*?)\s+）", r"（\1）", new)
        cnt = len(LINK_INSERTED.findall(txt))
        n += cnt
        if not dry and cnt:
            open(path, "w", encoding="utf-8").write(new)
        log(f"[hn] {'(dry) ' if dry else ''}{os.path.basename(path)}：剥离 {cnt}")
    log(f"[hn] 合计剥离 {n} 条")
    return n


def backfill(since: str | None, dry: bool, refresh: bool) -> tuple[int, int, int]:
    cache = load_cache()
    files = sorted(glob.glob(os.path.join(VAULT, "20*.md")))
    if since:
        files = [f for f in files if os.path.basename(f)[:10] >= since]
    n_patch = n_skip = n_miss = n_lowconf = 0
    for path in files:
        txt = open(path, encoding="utf-8").read()
        lines = txt.splitlines()
        changed = 0
        for i, ln, url in list(iter_items(txt)):
            frag = (HN_FRAG.search(ln) or [None, ""])[1] if HN_FRAG.search(ln) else ""
            want = recorded_score(frag)
            h = lookup(url, cache, refresh=refresh)
            # 置信度：讨论页分数不会比采集时更小（分数只涨不跌）。明显更小 → 不是同一条帖
            if h and want and (h.get("points") or 0) < want * 0.5:
                t = MD_LINK.search(ln)
                ent_title = (t.group(1) if t else "")
                block = "\n".join(lines[i:i + 12])      # 条目正文（含引号内的 HN 帖名）
                brief_date = os.path.basename(path)[:10]
                # 简报记的分数属于「另一个 URL 的同题材帖」时优先链那条（讨论在那儿）
                h2 = related_thread_lookup(url, ent_title, want, cache,
                                           extra_queries=quoted_titles(block),
                                           brief_date=brief_date)
                if not h2:
                    h2 = title_lookup(ent_title, want, cache, article_url=url)
                if h2:
                    h = h2
                else:
                    # 找不到同题材帖 → 退回文章自己的讨论串（分数与简报不同，但讨论确实在那儿）
                    log(f"[hn] 分数对不上但保留文章自己的讨论串（简报 {want} 分 / 帖 "
                        f"{h.get('points')} 分）：{(t.group(1) if t else '')[:60]}  {os.path.basename(path)}")
                    n_lowconf += 1
            if not h:
                n_miss += 1
                continue
            new = patch_line(lines[i], h)
            if new is None:
                n_skip += 1
                continue
            lines[i] = new
            changed += 1
            n_patch += 1
        if changed and not dry:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        if changed:
            log(f"[hn] {'(dry) ' if dry else ''}{os.path.basename(path)}：补 {changed} 条讨论链接")
    save_cache(cache)
    log(f"[hn] 合计：新增 {n_patch} · 已有/无需 {n_skip} · 未匹配 {n_miss} · 低置信跳过 {n_lowconf}"
        f"（文件 {len(files)} 份）")
    return n_patch, n_skip, n_miss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["lookup", "backfill", "reset"])
    ap.add_argument("url", nargs="?")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--since")
    ap.add_argument("--refresh", action="store_true", help="忽略缓存重新查")
    a = ap.parse_args()
    if a.mode == "reset":
        reset(a.since, a.dry)
        return
    if a.mode == "lookup":
        if not a.url:
            sys.exit("需要 url")
        cache = load_cache()
        h = lookup(a.url, cache, refresh=True)
        save_cache(cache)
        print(json.dumps(h, ensure_ascii=False, indent=1) if h else "未找到")
        return
    backfill(a.since, a.dry, a.refresh)


if __name__ == "__main__":
    main()
