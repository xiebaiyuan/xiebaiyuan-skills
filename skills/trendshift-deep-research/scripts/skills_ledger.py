#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Skill 总表台账生成器（skills.sh / Agent Skills 生态）

背景：`调研分析/SKILLS/` 下有 index.md（手写巨型索引）+ 榜单/（每日简报 40 份），
`调研分析/Skill与插件/` 有 340+ 份单项目调研文档。三者分散，查一个 skill
要翻三个地方。本脚本把它们合并成一张「Skill 总表」，每天随榜单向导更新。

数据来源（全部本地，除星数是 gh api 实时拉）：
  1. 调研分析/Skill与插件/*.md      —— 单项目调研文档（repo / 日期 / 星数 / 「解决的问题」一句话）
  2. 调研分析/SKILLS/index.md       —— 人工分类（官方·平台 / 聚合仓库 / 独立 skill / 风险样本）+ 策展要点
  3. 调研分析/SKILLS/榜单/*.md      —— 每日榜单简报（日期 → 首次收录 / 最近上榜）
  4. gh api repos/<o>/<r>          —— 实时星数（带缓存，只在缓存过期时刷新）

用法：
    python skills_ledger.py update      # 每日：重建总表（星数缓存过期时自动刷新）
    python skills_ledger.py update --no-stars   # 不拉星数，全用缓存
    python skills_ledger.py check       # 质量门禁：每条是否都有中文「干啥的」
    python skills_ledger.py report      # 只打印统计
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))       # skill 目录
DATA = os.path.join(BASE, "data")
STARS_CACHE = os.path.join(DATA, "skills_stars.json")
LEDGER_JSON = os.path.join(DATA, "skills_ledger.json")
MANUAL = os.path.join(DATA, "skills_manual.json")

VAULT = os.path.expanduser("~/AI_DOC/调研分析")
SKILLS_DIR = os.path.join(VAULT, "SKILLS")
BRIEF_DIR = os.path.join(SKILLS_DIR, "榜单")
INDEX_MD = os.path.join(SKILLS_DIR, "index.md")
DOC_DIR = os.path.join(VAULT, "Skill与插件")
OUT_MD = os.path.join(SKILLS_DIR, "00-Skill 总表.md")

CJK = re.compile(r"[\u4e00-\u9fff]")
GH_URL = re.compile(r"https?://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?=[\s\)\]/|,;，。]|$)")

# 人工覆盖层里没写分类时的兜底：按仓库名 / 文档标签推断
CAT_RULES = [
    ("官方/平台", ["官方", "official", "platform"]),
    ("聚合仓库", ["聚合", "aggregat", "bundle", "collection"]),
    ("独立 skill", []),
]
DEFAULT_CAT = "独立 skill"

# index.md 章节名 → 分类（人工分类优先，脚本只做映射）
SECTION_CAT = {
    "官方/平台系": "官方/平台",
    "聚合仓库系": "聚合仓库",
    "独立 skill 系": "独立 skill",
    "🔴 平台风险与反灌水（2026-09-11 起）": "风险样本",
    "平台风险与反灌水（2026-09-11 起）": "风险样本",
    "4.1 官方/大厂系列": "官方/平台",
    "4.2 设计类": "独立 skill",
    "4.3 框架/平台类": "独立 skill",
    "4.4 垂直领域类": "独立 skill",
}

# 领域/主题（按关键词打分，[推断]，可用 manual 覆盖）
TOPIC_RULES = [
    ("设计前端", {"design": 3, "ui": 3, "ux": 3, "css": 3, "animation": 3, "前端": 3, "设计": 3,
                  "figma": 3, "tailwind": 2, "component": 2, "impeccable": 2, "slop": 2,
                  "taste": 2, "accessib": 2}),
    ("内容创作", {"writing": 3, "editing": 3, "写作": 3, "文案": 3, "seo": 3, "marketing": 3,
                  "营销": 3, "公众号": 3, "小红书": 2, "创作": 2, "content": 2, "social": 2}),
    ("多媒体生成", {"video": 3, "audio": 3, "music": 3, "image": 3, "视频": 3, "音频": 3, "音乐": 3,
                    "图像": 3, "media": 2, "cad": 3, "3d": 2, "hyperframe": 3}),
    ("数据与金融", {"finance": 3, "stock": 3, "金融": 3, "股票": 3, "trading": 3, "sql": 2,
                    "database": 2, "数据": 2, "analytics": 2, "市场": 2}),
    ("安全与审计", {"security": 3, "安全": 3, "audit": 3, "审计": 3, "vulnerab": 3, "pentest": 3,
                    "scan": 2, "osint": 3, "reverse": 2, "渗透": 3}),
    ("测试与质量", {"test": 3, "测试": 3, "qa": 3, "review": 2, "quality": 2, "质量": 3,
                    "eval": 3, "lint": 2, "验证": 2, "debug": 2}),
    ("工程规范", {"typescript": 2, "python": 2, "golang": 3, "rust": 2, "kotlin": 3, "swift": 3,
                  "convention": 3, "best-practice": 3, "规范": 3, "code": 1, "refactor": 2,
                  "architecture": 2, "架构": 3, "monorepo": 2}),
    ("平台 SDK 技能", {"vercel": 2, "supabase": 3, "stripe": 3, "firebase": 3, "cloudflare": 3,
                       "azure": 3, "aws": 3, "google": 2, "clickhouse": 3, "neon": 3, "expo": 3,
                       "插桩": 2, "integrat": 2, "sdk": 2, "api": 1}),
    ("办公协作", {"office": 3, "sheet": 3, "docx": 3, "excel": 3, "办公": 3, "word": 2, "slide": 2,
                  "meeting": 2, "会议": 2, "email": 2, "邮件": 3, "calendar": 2, "notion": 3,
                  "文档": 2, "lark": 3, "feishu": 3, "wecom": 3, "钉钉": 3}),
    ("研究调查", {"research": 3, "研究": 3, "paper": 3, "论文": 3, "survey": 2, "osint": 3,
                  "search": 2, "搜索": 2, "crawl": 2, "抓取": 2, "nature": 2, "academic": 3}),
    ("记忆上下文", {"memory": 3, "context": 2, "记忆": 3, "上下文": 3, "rag": 3, "knowledge": 2}),
    ("运维部署", {"devops": 3, "deploy": 3, "docker": 3, "kubernetes": 3, "k8s": 3, "ci": 2,
                  "terraform": 3, "observab": 3, "可观测": 3, "grafana": 3, "部署": 3}),
    ("浏览器与桌面自动化", {"browser": 3, "浏览器": 3, "playwright": 3, "puppeteer": 3,
                            "computer-use": 3, "desktop": 2, "自动化": 2, "device": 2, "mobile": 2}),
    ("方法论与元技能", {"skill-creator": 3, "meta": 2, "methodolog": 3, "方法论": 3, "workflow": 2,
                        "superpower": 3, "taste": 2, "discipline": 3, "纪律": 3, "gate": 2}),
]

FIELD_DOC = """| 列 | 含义 |
|:--|:--|
| 项目 | 真实 GitHub `owner/repo`（skills.sh 展示名与真实 repo 常不一致，本表一律用实测真实名） |
| 分类 | 官方/平台 · 聚合仓库 · 独立 skill · 风险样本（来自 index.md 的人工分类，可被 manual.json 覆盖） |
| 来源 | 该文档来自哪条调研主线：`skills.sh`（安装量榜）/ `Trendshift`（GitHub 热度）/ 两者 |
| 星数 | `gh api` 实时拉取（带缓存，日期见页首）；未入库/私有/非 GitHub 源为「—」 |
| 领域 | 按仓库名/描述关键词自动归类 [推断]，可用 manual.json 的 `topic` 覆盖 |
| 首次收录 | 第一次出现在调研文档或榜单简报中的日期 |
| 最近上榜 | 最近一次出现在榜单简报中的日期（空 = 只在调研文档里出现过） |
| 榜单席位 | 该 repo 在榜单简报中累计被提及的次数（不是安装量） |
| 调研文档 | 已产出的单项目调研文档（没有 = 只进过榜单、还没建档） |
| 干啥的 | 一句话说明解决什么问题：优先取调研文档里的「**解决的问题**」，其次 index.md 策展要点，最后 manual.json 的 `desc` |
"""


def log(*a):
    print(*a, file=sys.stderr)


def load_manual() -> dict:
    if os.path.exists(MANUAL):
        with open(MANUAL, encoding="utf-8") as f:
            return json.load(f)
    return {}


# ---------------------------------------------------------------- 解析：调研文档

STAR_PATTERNS = [
    re.compile(r"\|\s*Stars?\s*\|[^|\n]*?([\d][\d,]{0,9})"),
    re.compile(r"([\d][\d,]{2,9})\s*⭐"),
]


def parse_doc(path: str) -> dict:
    fn = os.path.basename(path)
    txt = open(path, encoding="utf-8", errors="ignore").read()
    head = txt[:6000]
    repo = None
    seen = []
    for m in GH_URL.finditer(head):
        r = f"{m.group(1)}/{m.group(2)}".lower().rstrip(".,;")
        if r not in seen:
            seen.append(r)
    # 文件名里的 owner__repo 更可靠（自己定的命名规范）
    m = re.match(r"([A-Za-z0-9._-]+)__([A-Za-z0-9._-]+?)(?:\s*技术调研|\.md|$)", fn)
    if m:
        owner, base = m.group(1), m.group(2)
        base = re.sub(r"[-_][vV]?\d+(\.\d+)*$", "", base)      # skills-v1.2.0 → skills
        repo = f"{owner}/{base}".lower()
    if not repo and seen:
        repo = seen[0]
    date = None
    fm = re.match(r"^---\n(.*?)\n---", txt, re.S)
    if fm:
        d = re.search(r"(?:date|created):\s*(\d{4}-\d{2}-\d{2})", fm.group(1))
        date = d.group(1) if d else None
    stars = None
    for pat in STAR_PATTERNS:
        s = pat.search(head)
        if s:
            try:
                v = int(s.group(1).replace(",", ""))
                if 1 <= v <= 9999999:
                    stars = v
                    break
            except ValueError:
                pass
    problem = ""
    p = re.search(r"\*\*解决的问题\*\*[：:]\s*(.{10,600}?)(?:\n\s*\n|\n#{1,3}\s|\n\*\*|\Z)", txt, re.S)
    if p:
        problem = re.sub(r"\s+", " ", p.group(1)).strip()
    what = ""
    if not problem:
        w = re.search(r"\*\*(?:问题|痛点)\*\*[：:]\s*(.{10,600}?)(?:\n\s*\n|\n#{1,3}\s|\Z)", txt, re.S)
        if w:
            what = re.sub(r"\s+", " ", w.group(1)).strip()
    if not problem and not what:
        # 回落到「## 是什么 / 二、它是干什么的？」章节的第一句
        s = re.search(r"##\s*(?:一、|二、|三、)?\s*(?:是什么|它是干什么的|是什么 \+ 源链接)[^\n]*\n+(.{20,400}?)(?:\n\n|\n#)", txt, re.S)
        if s:
            what = re.sub(r"\s+", " ", s.group(1)).strip()
    if not problem and not what:
        # 再回落到概览表里的「定位 / 一句话」行
        s = re.search(r"\|\s*(?:定位|一句话|简介|它是什么)\s*\|([^|\n]{10,300})", txt)
        if s:
            what = re.sub(r"\s+", " ", s.group(1)).strip()
    if not problem and not what:
        # Trendshift 侧文档：「## 项目定位 / 项目概述 / 一句话摘要」章节首句
        s = re.search(r"##\s*(?:项目定位|项目概述|一句话摘要|项目简介)[^\n]*\n+(.{20,400}?)(?:\n\n|\n#)", txt, re.S)
        if s:
            what = re.sub(r"\s+", " ", s.group(1)).strip()
    return {"file": fn, "repo": repo, "date": date, "stars": stars,
            "desc": problem or what, "title": fn[:-3], "seen": seen[:3],
            "tags": (re.search(r"tags:\s*\[(.*?)\]", fm.group(1)).group(1).split(",")
                     if fm and re.search(r"tags:\s*\[(.*?)\]", fm.group(1)) else [])}


def parse_docs() -> dict:
    out = {}
    if not os.path.isdir(DOC_DIR):
        return out
    for fn in sorted(os.listdir(DOC_DIR)):
        if not fn.endswith(".md"):
            continue
        d = parse_doc(os.path.join(DOC_DIR, fn))
        if d["repo"]:
            out[d["repo"]] = d
    return out


# ---------------------------------------------------------------- 解析：index.md

LINK = re.compile(r"\[\[([^\]|]+?)(?:\\?\|([^\]]+))?\]\]")


def clean_md(s: str) -> str:
    s = LINK.sub(lambda m: (m.group(2) or m.group(1)), s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = s.replace("**", "").replace("⭐", "").replace("★", "")
    s = s.replace("|", "／")            # 表格里不能出现裸竖线
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def repo_from_index_cell(cells: list[str]) -> str:
    for c in cells:
        for m in re.finditer(r"\b([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)\b", c):
            a, b = m.group(1), m.group(2)
            if a.lower() in ("http", "https", "api", "github.com"):
                continue
            if not re.search(r"[A-Za-z]{2,}", a):
                continue                     # 1.3k/h、15/20 这类不是仓库
            if len(b) < 3 or re.fullmatch(r"[a-z]{1,2}", b):
                continue
            if re.fullmatch(r"[\d.,]+[a-z]?", b):
                continue
            if (m.start() > 0 and c[m.start() - 1] == "/") or \
               (m.end() < len(c) and c[m.end()] == "/"):
                continue                     # "withgraphite/petergyang/jakubkrehel" 这类斜杠列表
            return f"{a}/{b}".lower()
    return ""


def doc_key_from_cell(cells: list[str]) -> str:
    for c in cells:
        m = LINK.search(c)
        if m:
            return m.group(1).split("/")[-1].strip()
    return ""


def parse_index() -> dict:
    """返回 {repo: {cat, curated_star, note, doc_key}}"""
    if not os.path.exists(INDEX_MD):
        return {}
    txt = open(INDEX_MD, encoding="utf-8").read()
    out = {}
    section = ""
    for ln in txt.splitlines():
        if ln.startswith("#"):
            section = ln.strip("# ").strip()
            continue
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) < 2 or set("".join(cells)) <= set("-: "):
            continue
        cat = SECTION_CAT.get(section, "")
        repo = repo_from_index_cell(cells)
        note = clean_md(cells[-1]) if len(cells) >= 3 else ""
        star = None
        sm = re.search(r"([\d][\d,]{2,9})\s*$|([\d][\d,]{2,9})", cells[-2] if len(cells) >= 3 else "")
        for c in cells:
            s = re.search(r"\*\*([\d][\d,]{2,9})\*\*|([\d][\d,]{2,9})\s*⭐", c)
            if s:
                try:
                    star = int((s.group(1) or s.group(2)).replace(",", ""))
                except ValueError:
                    pass
                break
        if not repo:
            continue
        rec = out.setdefault(repo, {"cat": "", "curated_star": None, "note": "", "doc_key": ""})
        if cat and not rec["cat"]:
            rec["cat"] = cat
        if star and not rec["curated_star"]:
            rec["curated_star"] = star
        if note and len(note) > len(rec["note"]):
            rec["note"] = note
        dk = doc_key_from_cell(cells)
        if dk and not rec["doc_key"]:
            rec["doc_key"] = dk
    return out


# ---------------------------------------------------------------- 解析：每日榜单简报

BRIEF_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.*)\.md$")


def parse_briefings(repos: set[str]) -> dict:
    """返回 {date: {"file": fn, "mentioned": set(repo)}}"""
    out = {}
    if not os.path.isdir(BRIEF_DIR):
        return out
    # 为每个 repo 准备匹配模式（owner/repo 全名 或 唯一 basename）
    base_count = Counter(r.split("/")[1] for r in repos)
    pats = {}
    for r in repos:
        owner, base = r.split("/")
        alts = [re.escape(r)]
        if base_count[base] == 1 and len(base) >= 8:
            alts.append(r"(?<![\w./-])" + re.escape(base) + r"(?![\w.-])")
        pats[r] = re.compile("|".join(alts), re.I)
    for fn in sorted(os.listdir(BRIEF_DIR)):
        m = BRIEF_RE.match(fn)
        if not m:
            continue
        date = m.group(1)
        txt = open(os.path.join(BRIEF_DIR, fn), encoding="utf-8", errors="ignore").read()
        hit = {r for r, p in pats.items() if p.search(txt)}
        out[date] = {"file": fn, "mentioned": hit, "bytes": len(txt)}
    return out


# ---------------------------------------------------------------- 星数刷新（gh api + 缓存）

def load_stars() -> dict:
    if os.path.exists(STARS_CACHE):
        with open(STARS_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def refresh_stars(repos: list[str], cache: dict, today: str, max_age_days: int = 1) -> dict:
    from concurrent.futures import ThreadPoolExecutor
    todo = []
    for r in repos:
        c = cache.get(r)
        if not c:
            todo.append(r)
            continue
        try:
            age = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(c["date"], "%Y-%m-%d")).days
        except Exception:
            age = 99
        if c.get("stars") is None and age < 7:      # 404/私有：7 天内不重试
            continue
        if age >= max_age_days:
            todo.append(r)

    def one(r):
        try:
            p = subprocess.run(["gh", "api", f"repos/{r}", "--jq", ".stargazers_count"],
                               capture_output=True, text=True, timeout=40)
            v = p.stdout.strip()
            if p.returncode == 0 and v.isdigit():
                return r, {"stars": int(v), "date": today}
            return r, {"stars": None, "date": today, "err": (p.stderr or "").strip()[:80]}
        except Exception as e:
            return r, {"stars": None, "date": today, "err": str(e)[:80]}

    if todo:
        log(f"[stars] 刷新 {len(todo)} 个仓库星数（缓存命中 {len(repos)-len(todo)}）…")
        with ThreadPoolExecutor(max_workers=8) as ex:
            for r, v in ex.map(one, todo):
                cache[r] = v
    ok = sum(1 for r in repos if (cache.get(r) or {}).get("stars") is not None)
    log(f"[stars] 有效星数 {ok}/{len(repos)}")
    return cache


# ---------------------------------------------------------------- 归类

def classify_topic(rec: dict) -> str:
    hay = " ".join([rec.get("repo", ""), rec.get("desc", ""), rec.get("note", ""),
                    " ".join(rec.get("tags", []))]).lower()
    scores = {}
    for topic, kws in TOPIC_RULES:
        s = 0
        for kw, w in kws.items():
            if not kw.isascii():
                if kw in hay:
                    s += w
            elif len(kw) >= 5:               # 长词允许前缀：financ* 命中 financial
                if re.search(r"(?<![a-z0-9])" + re.escape(kw), hay):
                    s += w
            elif re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", hay):
                s += w
        if s:
            scores[topic] = s
    if not scores:
        return "其他"
    return max(scores.items(), key=lambda kv: kv[1])[0]


def pick_desc(rec: dict, manual_desc: str) -> str:
    for c in (manual_desc, rec.get("desc", ""), rec.get("note", "")):
        c = (c or "").strip()
        if len(CJK.findall(c)) >= 4:
            return c
    return ""


# ---------------------------------------------------------------- 构建

def build(no_stars: bool = False) -> dict:
    today = datetime.now(CST).strftime("%Y-%m-%d")
    manual = load_manual()
    aliases = {k.lower(): v.lower() for k, v in manual.get("aliases", {}).items()}
    descs = manual.get("desc", {})
    cats = manual.get("cat", {})
    topics = manual.get("topic", {})
    notes = manual.get("notes", {})

    docs = parse_docs()                 # repo -> doc info
    idx = parse_index()                 # repo -> index 策展信息
    # 合并 repo 集合：调研文档 + index 提到的
    deny = {k.lower() for k in manual.get("deny", [])}
    repos = {r for r in (set(docs) | set(idx)) if r not in deny}
    for m in list(repos):
        if m in aliases:
            repos.discard(m)
            repos.add(aliases[m])
    briefs = parse_briefings(repos)

    ledger = {}
    for repo in sorted(repos):
        d = docs.get(repo, {})
        i = idx.get(repo, {})
        rec = {
            "repo": repo,
            "doc": d.get("file", ""),
            # index 的 wikilink 指向的文档名（可能与自己命名的调研文档不同名）
            "doc_key": i.get("doc_key", ""),
            "doc_date": d.get("date"),
            "doc_stars": d.get("stars"),
            "desc": pick_desc(
                {"repo": repo, "desc": d.get("desc", ""), "note": i.get("note", ""),
                 "tags": d.get("tags", [])},
                descs.get(repo, "")),
            "curated_star": i.get("curated_star"),
            "cat": cats.get(repo) or i.get("cat") or DEFAULT_CAT,
            "tags": d.get("tags", []),
            "mentions": 0, "first_brief": None, "last_brief": None,
        }
        if not rec["desc"]:              # manual desc 是最优先的兜底
            alt = descs.get(repo) or descs.get(repo.split("/")[1])
            if alt:
                rec["desc"] = alt
        ledger[repo] = rec

    # 榜单提及
    for date in sorted(briefs):
        for r in briefs[date]["mentioned"]:
            rec = ledger.get(r)
            if not rec:
                continue
            rec["mentions"] += 1
            if not rec["first_brief"] or date < rec["first_brief"]:
                rec["first_brief"] = date
            if not rec["last_brief"] or date > rec["last_brief"]:
                rec["last_brief"] = date

    # 星数
    cache = load_stars()
    if not no_stars:
        cache = refresh_stars(sorted(repos), cache, today)
        os.makedirs(DATA, exist_ok=True)
        with open(STARS_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=0)
    for repo, rec in ledger.items():
        c = cache.get(repo) or {}
        rec["stars"] = c.get("stars")
        rec["stars_date"] = c.get("date")
        if rec["stars"] is None and rec["doc_stars"]:
            rec["stars"] = rec["doc_stars"]
            rec["stars_src"] = "doc"

    for repo, rec in ledger.items():
        tg = [t.lower().strip() for t in rec.get("tags", [])]
        ss = "skills.sh" in tg
        tf = "trendshift" in tg
        rec["source"] = "两者" if (ss and tf) else ("skills.sh" if ss else ("Trendshift" if tf else "—"))
        rec["topic"] = topics.get(repo) or classify_topic(rec)
        rec["note"] = notes.get(repo, "")
        rec["first_seen"] = min([x for x in (rec["doc_date"], rec["first_brief"]) if x] or [""]) or ""
        rec["last_seen"] = max([x for x in (rec["doc_date"], rec["last_brief"]) if x] or [""]) or ""

    return {
        "generated_at": datetime.now(CST).strftime("%Y-%m-%d %H:%M"),
        "today": today,
        "entries": list(ledger.values()),
        "briefs": {k: {"file": v["file"], "n": len(v["mentioned"])} for k, v in briefs.items()},
        "doc_count": len([f for f in os.listdir(DOC_DIR) if f.endswith(".md")]) if os.path.isdir(DOC_DIR) else 0,
    }


# ---------------------------------------------------------------- 渲染

def fmt_stars(n) -> str:
    return f"{n:,}" if n else "—"


def trim_desc(s: str, limit: int = 96) -> str:
    s = clean_md(s)
    if len(s) > limit:
        cut = max(s.find("。"), s.find("；"), s.find("，", 40, limit))
        s = s[:cut + 1] if 30 <= cut <= limit else s[:limit - 1] + "…"
    return s


def render(led: dict, skip_nodoc: bool = False) -> str:
    ents = led["entries"]
    ranked = sorted(ents, key=lambda e: (-(e["stars"] or 0), -(e["mentions"] or 0), e["repo"]))
    with_doc = [e for e in ents if e["doc"] or e["doc_key"]]
    no_doc = [e for e in ents if not (e["doc"] or e["doc_key"])]
    risk = [e for e in ents if e["cat"] == "风险样本"]
    by_topic = Counter(e["topic"] for e in ents)
    by_cat = Counter(e["cat"] for e in ents)
    briefs = led["briefs"]

    A = []
    P = A.append
    P("---")
    P("type: moc")
    P("title: Skill 总表（skills.sh / Agent Skills 全量台账）")
    P("created: 2026-09-14")
    P(f"updated: {led['today']}")
    P("tags: [skills.sh, agent-skills, 索引, 台账, skill]")
    P("---")
    P("")
    P("# Skill 总表（skills.sh / Agent Skills 全量台账）")
    P("")
    P(f"> 由脚本 `~/.hermes/skills/research/trendshift-deep-research/scripts/skills_ledger.py` 生成，"
      f"最近生成 {led['generated_at']}（CST）。")
    P(f"> 数据来源：`Skill与插件/` 的 {led['doc_count']} 份调研文档 + `SKILLS/index.md` 的人工分类 + "
      f"`SKILLS/榜单/` 的 {len(briefs)} 份每日简报；星数是 `gh api` 实时值（刷新日 {led['today']}）。")
    P("> **每天跑完 skills.sh 榜单调研后执行 `python skills_ledger.py update`，新榜单与新调研自动并入本表。**")
    P("")
    P("## 一、总览")
    P("")
    P("| 指标 | 数值 |")
    P("|:--|:--|")
    P(f"| 收录条目（进过榜单或建过档） | **{len(ents)}** |")
    P(f"| 已出调研文档 | **{len(with_doc)}** |")
    P(f"| 只上榜、还没建档 | {len(no_doc)}（见第四节待办） |")
    P(f"| 官方/平台 · 聚合仓库 · 独立 skill · 风险样本 | "
      f"{by_cat.get('官方/平台',0)} · {by_cat.get('聚合仓库',0)} · "
      f"{by_cat.get('独立 skill',0)} · {by_cat.get('风险样本',0)} |")
    P(f"| 星数合计（能拉到星数的条目） | {sum(e['stars'] or 0 for e in ents):,} |")
    P(f"| 榜单简报覆盖 | {len(briefs)} 天（{min(briefs) if briefs else '—'} ~ {max(briefs) if briefs else '—'}） |")
    P("")
    P("## 二、领域分布（[推断] 自动归类）")
    P("")
    P("| 领域 | 条目数 | 头部代表 |")
    P("|:--|--:|:--|")
    for topic, cnt in by_topic.most_common():
        tops = [e for e in ranked if e["topic"] == topic][:3]
        rep = "、".join(f"{e['repo'].split('/')[-1]}（{fmt_stars(e['stars'])}）" for e in tops)
        P(f"| {topic} | {cnt} | {rep} |")
    P("")
    P("## 三、主台账（全量，按星数倒序）")
    P("")
    P("| 项目 | 分类 | 来源 | 星数 | 领域 | 首次收录 | 最近上榜 | 席位 | 调研文档 | 干啥的 |")
    P("|:--|:--|:--|--:|:--|:--|:--|--:|:--|:--|")
    for e in ranked:
        doc = f"[[调研分析/Skill与插件/{e['doc'][:-3]}\\|📄]]" if e["doc"] else (
            f"[[调研分析/Skill与插件/{e['doc_key'][:-3]}\\|📄]]" if e["doc_key"] else "—")
        P(f"| [{e['repo']}](https://github.com/{e['repo']}) | {e['cat']} | {e['source']} | {fmt_stars(e['stars'])} | "
          f"{e['topic']} | {(e['first_seen'] or '—')[5:]} | {(e['last_brief'] or '—')[5:]} | "
          f"{e['mentions'] or '—'} | {doc} | {trim_desc(e['desc'])} |")
    P("")
    P("## 四、只上榜、还没建档（待办清单）")
    P("")
    P(f"共 {len(no_doc)} 条。规则：**只抓榜单不调研 = 收集癖**——这些进过榜单但还没产出调研文档，"
      "按「官方技能 > 独立 skill > 聚合仓库」优先级补档。")
    P("")
    if no_doc:
        P("| 项目 | 分类 | 星数 | 最近上榜 | 席位 | 干啥的 |")
        P("|:--|:--|--:|:--|--:|:--|")
        for e in sorted(no_doc, key=lambda x: (-(x["stars"] or 0), -(x["mentions"] or 0))):
            P(f"| [{e['repo']}](https://github.com/{e['repo']}) | {e['cat']} | {fmt_stars(e['stars'])} | "
              f"{(e['last_brief'] or '—')[5:]} | {e['mentions'] or '—'} | {trim_desc(e['desc'])} |")
    P("")
    P("## 五、平台风险样本（镜像 / 灌水 / 映射异常）")
    P("")
    if risk:
        P("| 项目 | 星数 | 干啥的 |")
        P("|:--|--:|:--|")
        for e in sorted(risk, key=lambda x: -(x["stars"] or 0)):
            P(f"| [{e['repo']}](https://github.com/{e['repo']}) | {fmt_stars(e['stars'])} | {trim_desc(e['desc'], 120)} |")
    else:
        P("（暂无，人工分类在 index.md 的「平台风险与反灌水」节）")
    P("")
    P("> 检测规则：`gh api repos/<o>/<r>/contents/README.md --jq .sha` 与 `git/trees?recursive=1` 的 blob 数"
      "双双相同 → 判镜像。**判据是内容指纹不是星数。**")
    P("")
    P("## 六、榜单覆盖（每日并入情况）")
    P("")
    P("| 日期 | 当日提及条目 | 本次首次进表 | 累计条目 | 简报 |")
    P("|:--|--:|--:|--:|:--|")
    first_seen_by_day = Counter(e["first_seen"] for e in ents if e["first_seen"])
    cum = 0
    for date in sorted(briefs):
        new = first_seen_by_day.get(date, 0)
        cum += new
        fn = briefs[date]["file"][:-3]
        P(f"| {date} | {briefs[date]['n']} | {new} | {cum} | "
          f"[[调研分析/SKILLS/榜单/{fn}\\|{date} 简报]] |")
    P("")
    P("## 字段说明")
    P("")
    P(FIELD_DOC.strip())
    P("")
    P("## 维护")
    P("")
    P("```bash")
    P("S=~/.hermes/skills/research/trendshift-deep-research/scripts/skills_ledger.py")
    P("python $S update          # 每日：刷新星数 + 重建总表")
    P("python $S update --no-stars   # 不联网，纯本地")
    P("python $S check           # 质量门禁（缺中文描述 / 缺分类）")
    P("python $S report          # 只打印统计")
    P("```")
    P("")
    P("人工覆盖层：`data/skills_manual.json`（脚本不覆盖）——`desc` 一句话、`cat` 分类、`topic` 领域、"
      "`aliases` 改名映射、`notes` 备注。")
    P("")
    P("## 关联")
    P("")
    P("- [[调研分析/SKILLS/index|SKILLS 总索引（人工分类与生态目录）]]")
    P("- [[调研分析/SKILLS/榜单|每日榜单简报目录]]")
    P("- [[调研分析/Skill与插件|单项目调研文档目录]]")
    P("- 姊妹台账：[[调研分析/DeepSeek Harness/dsh插件每日雷达/00-插件总表|dsh 插件总表]]")
    P("")
    return "\n".join(A) + "\n"


# ---------------------------------------------------------------- 门禁 / main

def check(led: dict, since: str | None = None) -> int:
    ents = led["entries"]
    if since:
        ents = [e for e in ents if e["first_seen"] >= since]
    no_desc = [e for e in ents if len(CJK.findall(e.get("desc") or "")) < 4]
    no_cat = [e for e in ents if not e.get("cat")]
    log(f"[check] 范围 {'自 ' + since + ' 起' if since else '全表'} {len(ents)} 条")
    if no_desc:
        log(f"[check] ✗ {len(no_desc)} 条缺中文「干啥的」→ 补进 data/skills_manual.json 的 desc：")
        for e in no_desc[:40]:
            log(f"        {e['repo']}  {fmt_stars(e['stars'])}  文档={e['doc'] or e['doc_key'] or '无'}")
    else:
        log("[check] ✓ 中文描述齐全")
    if no_cat:
        log(f"[check] ✗ {len(no_cat)} 条缺分类：{', '.join(e['repo'] for e in no_cat[:10])}")
    else:
        log("[check] ✓ 分类齐全")
    nodoc = [e for e in ents if not (e["doc"] or e["doc_key"])]
    if nodoc:
        log(f"[check] ⚠ {len(nodoc)} 条只上榜未建档（不阻塞，见总表第四节待办）")
    bad = len(no_desc) + len(no_cat)
    log(f"[check] {'通过' if bad == 0 else '未通过，问题 %d 项' % bad}")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["update", "rebuild", "check", "report"])
    ap.add_argument("--no-stars", action="store_true", help="不刷新星数（用缓存）")
    ap.add_argument("--since", help="check：只查此日期之后首次进表的条目")
    args = ap.parse_args()

    led = build(no_stars=args.no_stars or args.mode in ("check", "report"))
    ents = led["entries"]
    log(f"[ledger] 条目 {len(ents)} | 已建档 {len([e for e in ents if e['doc'] or e['doc_key']])} "
        f"| 简报 {len(led['briefs'])} 份 | 文档总数 {led['doc_count']}")
    if args.mode == "check":
        sys.exit(1 if check(led, args.since) else 0)
    md = render(led)
    if args.mode == "report":
        print(md)
        return
    os.makedirs(DATA, exist_ok=True)
    with open(LEDGER_JSON, "w", encoding="utf-8") as f:
        json.dump({"generated_at": led["generated_at"], "today": led["today"],
                   "briefs": led["briefs"], "doc_count": led["doc_count"],
                   "entries": led["entries"]}, f, ensure_ascii=False, indent=1)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(md)
    log(f"[ledger] 写入 {OUT_MD}（{len(md.encode('utf-8'))} bytes）")


if __name__ == "__main__":
    main()
