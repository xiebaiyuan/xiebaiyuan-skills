#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dsh 插件总表台账生成器

背景：dsh 插件每日雷达已跑 20+ 天，每天一份日报（`dsh插件每日雷达/YYYY-MM-DD.md`）。
本脚本把历史日报里出现过的所有插件/项目汇总成一张「插件总表」（vault: 00-插件总表.md），
并与 dsh.fish 注册中心快照（10k+ 条目，带 stars / 星速 / 评级 / 类型）对齐，
之后每天跑一次把当天日报的内容并进来。

用法：
    python dsh_ledger.py rebuild           # 全量重建（扫所有日报 + 拉快照）
    python dsh_ledger.py update            # 每日增量（同 rebuild，但保留 changelog 历史）
    python dsh_ledger.py update --offline  # 用本地缓存快照，不联网
    python dsh_ledger.py report            # 只打印统计，不写文件

状态数据（aliases / 赛道覆盖 / 人工备注）在 data/manual.json，脚本不会覆盖它。
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
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # skill 目录
DATA = os.path.join(BASE, "data")
SNAP_CACHE = os.path.join(DATA, "snapshot.json")
LEDGER_JSON = os.path.join(DATA, "ledger.json")
MANUAL = os.path.join(DATA, "manual.json")
REPORT_DIR = os.path.expanduser(
    "~/AI_DOC/调研分析/DeepSeek Harness/dsh插件每日雷达")
DEEPDIVE_DIR = os.path.expanduser("~/AI_DOC/调研分析/DeepSeek Harness/深度调研")
OUT_MD = os.path.join(REPORT_DIR, "00-插件总表.md")
SNAPSHOT_API = "https://dsh.fish/api/v1/catalog/snapshot"

# ---------------------------------------------------------------- 常量配置

# 噪声 token（正则解析日报表格时的误命中）
DENY_KEYS = {
    "ssh/sftp", "word/excel", "bundle/skill", "git/trees", "pro/max",
    "agent/pre-step", "chatgpt/codex", "agents.md/rules", "search/repositories",
    "dataversion/generatedat", "evaluation/dsh-minimal.patch",
    "dshplugin.app/browsers", "dsh-plugins.net/zh", "198/1d", "162/1d",
    "api/search", "skills/mcp", "universal/robots", "见/日报",
}

# 赛道分类：加权关键词打分，最高分胜出；ASCII 关键词按词边界匹配（防 skill 里命中 kill）
# 权重 3 = 强特征（专指该赛道），1 = 弱特征（泛词）
TRACK_RULES = [
    ("沙箱与安全", {
        "sandbox": 3, "redteam": 3, "red-team": 3, "purge": 3, "jailbreak": 3, "permission": 3,
        "guard": 3, "firewall": 3, "audit": 3, "credential": 3, "cipher": 3, "antivirus": 3,
        "越狱": 3, "破甲": 3, "权限": 3, "隔离": 3, "鉴权": 2,
        "security": 1, "secure": 1, "safe": 1, "secret": 1, "安全": 1, "vault": 1}),
    ("记忆与上下文", {
        "memory": 3, "recall": 3, "mem0": 3, "mnemos": 3, "rag": 3, "deja": 3, "compaction": 2,
        "context": 2, "knowledge": 2, "milvus": 3, "anchor": 2, "记忆": 3, "上下文": 3,
        "蒸馏": 2, "知识库": 3}),
    ("市场与索引", {
        "marketplace": 3, "registry": 3, "catalog": 3, "radar": 3, "plugin-market": 3,
        "market": 2, "store": 2, "hub": 2, "市场": 3, "索引": 2, "收录": 2}),
    ("界面与皮肤", {
        "theme": 3, "skin": 3, "sidebar": 3, "background": 3, "dashboard": 3, "widget": 3,
        "overlay": 3, "tui": 3, "gui": 3, "desktop": 3, "hud": 3, "layout": 2, "panel": 2,
        "theme": 3, "皮肤": 3, "界面": 3, "主题": 3, "桌面": 3, "侧栏": 3, "背景": 3,
        "ui": 1, "web": 1}),
    ("视觉与多模态", {
        "vision": 3, "ocr": 3, "screenshot": 3, "dictation": 3, "microphone": 3, "camera": 3,
        "comfyui": 3, "video": 2, "voice": 2, "speech": 2, "tts": 2, "image": 2, "audio": 2,
        "视觉": 3, "语音": 3, "截图": 3, "图像": 2, "视频": 2, "画布": 2}),
    ("搜索与浏览", {
        "browser": 3, "tavily": 3, "zhihu": 3, "crawl": 3, "scrape": 3, "search": 3,
        "fetch": 2, "搜索": 3, "浏览": 3, "抓取": 2}),
    ("提供商与路由", {
        "provider": 3, "router": 3, "routing": 3, "ollama": 3, "openai": 2, "codex": 2,
        "claude": 2, "anthropic": 2, "gemini": 2, "subscription": 3, "oauth": 3,
        "路由": 3, "订阅": 3, "模型接入": 3, "api key": 2}),
    ("多Agent与编排", {
        "subagent": 3, "orchestrat": 3, "swarm": 3, "autofork": 3, "delegate": 2,
        "planner": 2, "agent": 1, "编排": 3, "分叉": 3, "多智能体": 3}),
    ("会话与终端", {
        "terminal": 3, "shell": 3, "replay": 3, "transcript": 3, "session": 2, "chat": 2,
        "conversation": 2, "drawer": 2, "会话": 3, "终端": 3}),
    ("运维与可观测", {
        "otel": 3, "telemetry": 3, "doctor": 3, "budget": 3, "spend": 3, "usage": 2,
        "cost": 2, "token": 2, "monitor": 2, "metric": 2, "health": 1, "backup": 2,
        "用量": 3, "成本": 2, "观测": 3, "监控": 2, "计费": 3, "备份": 2}),
    ("接入与互操作", {
        "feishu": 3, "lark": 3, "dingtalk": 3, "imessage": 3, "wechat": 3, "wecom": 3,
        "slack": 3, "telegram": 3, "sftp": 3, "ssh": 3, "acp": 3, "tunnel": 3, "mcp": 2,
        "bridge": 2, "gateway": 2, "email": 3, "notify": 2, "remote": 2, "接入": 3,
        "通知": 2, "邮件": 3, "互通": 3, "远程": 2}),
    ("创作与娱乐", {
        "tavern": 3, "roleplay": 3, "character": 3, "preset": 2, "novel": 3, "comic": 3,
        "game": 3, "music": 3, "角色": 3, "扮演": 3, "游戏": 3, "小说": 3, "陪伴": 3, "创作": 2}),
    ("配置与治理", {
        "governance": 3, "lint": 3, "policy": 2, "rules": 2, "template": 2, "standard": 2,
        "config": 2, "settings": 2, "prompt": 2, "gate": 2, "openspec": 3,
        "规则": 3, "治理": 3, "配置": 2, "规范": 2, "skill": 1}),
    ("文件与工作区", {
        "worktree": 3, "workspace": 3, "office": 3, "excel": 3, "xlsx": 3, "docx": 3,
        "archive": 3, "undo": 3, "git": 2, "todo": 2, "snapshot": 2, "file": 2, "task": 1,
        "文件": 2, "工作区": 3, "快照": 3, "归档": 3, "目录": 2}),
    ("效率自动化", {
        "workflow": 3, "pipeline": 2, "automation": 3, "schedule": 2, "cron": 3,
        "自动化": 3, "流程": 2, "自动": 2}),
]
DEFAULT_TRACK = "其他"

# dsh.fish categories → 本表赛道（弱信号）
CAT_TRACK = {
    "ui": "界面与皮肤", "theme": "界面与皮肤", "session": "会话与终端", "git": "文件与工作区",
    "remote": "接入与互操作", "memory": "记忆与上下文", "search": "搜索与浏览",
    "vision": "视觉与多模态", "provider": "提供商与路由", "marketplace": "市场与索引",
}

# 生态基建 / 跨生态参考（不算「插件」，单独一节，脚本按 key 匹配）
INFRA_KEYS = {
    "deepseek-ai/deepseek-harness": "上游主仓：DeepSeek Harness 本体",
    "dshplugin/dsh-plugin-hub": "社区内置插件市场（registry）",
    "bradegithub/dsh-plugins-marketplace": "第三方插件市场",
    "v1ki/dsh-plugin-subscriptions": "订阅接入市场（Codex/Claude/Grok）",
    "stvlynn/dsh.fish": "官方钦定插件注册中心（评分 S/A/B/C + CLI）",
    "dsh-market/dsh-market": "社区插件市场",
    "noob-stupid/dsh-plugin-hub": "插件 hub 早期实现",
    "beancookie/awesome-dsh-plugin": "精选列表",
    "adamplatin123/awesome-dsh-plugins": "雷达式精选（先收录后测试）",
    "anywhere-labs/dsh-desktop": "Electron 桌面客户端（高星，本身也是插件）",
    "nexu-io/open-design": "跨生态高星项目（设计，带 dsh topic）",
    "ruvnet/ruflo": "跨生态高星项目（Agent 编排）",
    "esengine/deepseek-reasonix": "终端编码 Agent（带 dsh topic）",
    "strukto-ai/mirage": "统一虚拟文件系统（生态基建）",
    "volcengine/openviking": "记忆/上下文基建（火山引擎）",
    "tencent/weknora": "知识库基建（腾讯）",
    "alibaba/anolisa": "阿里 ANOLISA（企业级接入）",
    "agentrq/agentrq": "Agent 队列/基建黑马",
    "zju-real/polaris": "自主科学发现（浙大）",
    "hashgraph-online/hol-guard": "Agent 运行时安全防护",
}

FIELD_DOC = """| 列 | 含义 |
|:--|:--|
| 插件 | 注册中心 id 或 `owner/repo` 短名 |
| 类型 | dsh.fish 探测的实际加载形态：bundle / skill / agent-preset / profile |
| 星数 | dsh.fish 快照抓取时的 stars（非实时，抓取时间见页首） |
| 7日星速 | dsh.fish `starVelocity7d`（30 日字段全库为 0，不可用） |
| 评级 | dsh.fish 综合分 S/A/B/C（popularity 0.4 + maintenance 0.3 + quality 0.3，不含合规风险） |
| 赛道 | 本表按名称/简介/关键词自动归类，[推断]，可用 manual.json 覆盖 |
| 首次/最近 | 该条目第一次 / 最近一次出现在日报中的日期 |
| 状态 | 深调研（已出 ≥8KB 调研文档）/ 头部（≥1000★）/ 成长（星速≥20）/ 活跃（≥10★）/ 观察（<10★）/ 未入库（dsh.fish 未收录） |
| 一句话 | 干啥的。优先级：`manual.json` 的 `desc` 人工描述 > 日报原句 > 注册中心 summary；超过 90 字只留第一句 |
"""


# ---------------------------------------------------------------- 工具

def log(*a):
    print(*a, file=sys.stderr)


def load_manual() -> dict:
    if os.path.exists(MANUAL):
        with open(MANUAL, encoding="utf-8") as f:
            return json.load(f)
    return {}


def fetch_snapshot(offline: bool = False) -> dict:
    os.makedirs(DATA, exist_ok=True)
    if not offline:
        tmp = SNAP_CACHE + ".tmp"
        try:
            subprocess.run(["curl", "-sS", "--max-time", "120", SNAPSHOT_API, "-o", tmp],
                           check=True)
            with open(tmp, encoding="utf-8") as f:
                head = f.read(200)
            if '"artifacts"' not in head:
                raise RuntimeError("快照响应异常：" + head[:120])
            os.replace(tmp, SNAP_CACHE)
            log("[snapshot] 已更新 ->", SNAP_CACHE)
        except Exception as e:  # 网络失败回落缓存，不编数据
            log(f"[snapshot] 拉取失败（{e}），改用本地缓存 {SNAP_CACHE}")
    with open(SNAP_CACHE, encoding="utf-8") as f:
        return json.load(f)


GH_URL = re.compile(r"https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?$")


def snapshot_indexes(snap: dict):
    by_full, by_base, by_id = {}, defaultdict(list), {}
    for a in snap["artifacts"]:
        u = a.get("sourceUrl") or ""
        m = GH_URL.match(u)
        if m:
            full = f"{m.group(1)}/{m.group(2)}".lower()
            by_full[full] = a
            by_base[m.group(2).lower()].append(a)
        by_id[a["id"].lower()] = a
    return by_full, by_base, by_id


def full_of(art: dict) -> str | None:
    m = GH_URL.match(art.get("sourceUrl") or "")
    return f"{m.group(1)}/{m.group(2)}".lower() if m else None


# ---------------------------------------------------------------- 日报解析

GH_IN_LINE = re.compile(r"github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\)|\s|\]|\.git|/|$)")
PLAIN_PAIR = re.compile(r"(?<![\w/.\-])([A-Za-z0-9][\w.\-]{1,38})/([A-Za-z0-9][\w.\-]{1,38})(?![\w/.\-])")
SLUG = re.compile(r"(?<![\w@/\-])(@[a-z0-9][\w.\-]*/[\w.\-]+|dsh[_\-][\w.\-]{2,}|DSH[_\-][\w.\-]{2,})")
MANIFEST = re.compile(r"```dsh-ledger\s*\n(.*?)```", re.S)
STAR = re.compile(r"\*{0,2}([\d,]{2,7})\s*(?:★|⭐|stars?)")
CJK = re.compile(r"[\u4e00-\u9fff]")


def looks_like_noise(fp: str) -> bool:
    if fp in DENY_KEYS:
        return True
    a, b = fp.split("/")
    if re.fullmatch(r"[\d,]+", a) and re.fullmatch(r"[a-z]{0,2}\d+[a-z]{0,2}", b):
        return True          # 形如 194/1d、575/c5（来自 "（+194/1d）"、"675/c5" 这类差分表述）
    for part in (a, b):
        if len(part) < 2:
            return True
        if any(ch.isdigit() for ch in part) and "." in part:
            return True
    if b.endswith((".md", ".json", ".py", ".patch")):
        return True
    return False


OWNER_HINT = re.compile(r"([A-Za-z0-9][\w.\-]{2,})\s*[（(]([A-Za-z0-9][\w.\-]{1,38})[)）]")


LINER_BAD = re.compile(
    r"(\[\[|vault 已有|^\s*\[源|持平|见日报|同上|见上|^—+$|topic\s|dsh\.fish\s+\d)")
LINER_JUNK = {"持平", "新增", "更新", "信息更新", "无", "同上", "见上", "—", "-"}


def _cell_ok(plain: str) -> bool:
    if not plain or set(plain) <= set("-: "):
        return False
    if plain in LINER_JUNK or len(plain) < 6:
        return False
    if LINER_BAD.search(plain):
        return False
    digits = sum(ch.isdigit() for ch in plain)
    if digits / len(plain) > 0.45:
        return False
    return True


def _one_liner(cells: list[str], name_tokens: set[str]) -> str:
    """从表格行里挑最有信息量的中文说明列。"""
    best = ""
    for c in cells:
        plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", c).strip("*_ `")
        if not plain or plain.lower() in name_tokens or STAR.fullmatch(plain.strip()):
            continue
        if not _cell_ok(plain):
            continue
        n_cjk = len(CJK.findall(plain))
        if n_cjk == 0:
            continue
        score = n_cjk * 2 + len(plain) / 40
        if score > len(best):
            best = plain
    if not best:  # 没有合适的中文列时退回最长英文列
        for c in cells:
            plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", c).strip("*_ `")
            if plain and not STAR.fullmatch(plain) and plain.lower() not in name_tokens \
               and _cell_ok(plain) and len(plain) > len(best):
                best = plain
    return re.sub(r"\s+", " ", best)[:180]


def parse_manifest(text: str):
    """日报末尾的 ```dsh-ledger 块（推荐格式）：
       仓库 | 星数 | 赛道 | 一句话
    """
    rows = []
    for block in MANIFEST.findall(text):
        for ln in block.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            parts = [p.strip() for p in ln.split("|")]
            if len(parts) < 2:
                continue
            rows.append(parts)
    return rows


def scan_report(path: str):
    """返回 (普通条目 dict, manifest 条目 list)"""
    date = os.path.basename(path)[:10]
    text = open(path, encoding="utf-8").read()
    entries = {}  # key -> {mentions, one_liner, stars}
    for ln in text.splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        name_tokens = set()
        found = set()
        for o, r in GH_IN_LINE.findall(ln):
            found.add(f"{o}/{r}".lower())
            name_tokens.add(f"{o}/{r}".lower())
        for o, r in PLAIN_PAIR.findall(ln):
            if "github.com" in o.lower():
                continue
            found.add(f"{o}/{r}".lower())
        # 去掉 topic:dsh-plugin / topics/dsh-plugin 这类「话题名」，否则会被误当成插件名
        slug_line = re.sub(r"(?:topic:|topics/)\s*[\w.\-]+", " ", ln)
        slugs = [t.lower().lstrip("@") for t in SLUG.findall(slug_line)]
        for tok in slugs:
            name_tokens.add(tok)
        one = _one_liner(cells, name_tokens)
        star = None
        sm = STAR.search(ln)
        if sm:
            try:
                star = int(sm.group(1).replace(",", ""))
            except ValueError:
                star = None
        found_ok = [fp for fp in found if not looks_like_noise(fp)]
        many = len(set(found_ok) | set(slugs)) > 1     # 一行提多个 → 星数与描述无法归属，都不用
        if many:
            star = None
            one = ""
        for fp in found_ok:
            e = entries.setdefault(fp, {"mentions": 0, "one_liner": "", "stars": None})
            e["mentions"] += 1
            if one and (not e["one_liner"] or len(one) > len(e["one_liner"])):
                e["one_liner"] = one
            if star and not e["stars"]:
                e["stars"] = star
        pair_parts = {p for fp in found_ok for p in fp.split("/")}
        for tok in slugs:
            if len(tok) < 6 or tok in GENERIC_SLUGS:
                continue
            if tok in pair_parts:
                continue          # owner/repo 里的 owner（dsh-market/dsh-market）别当独立插件
            if re.search(r"\.(net|com|dev|app|org|io|fish|cn|ai|sh)$", tok):
                continue          # 站点名（dsh-plugins.net 之类）不是插件
            e = entries.setdefault("~" + tok, {"mentions": 0, "one_liner": "", "stars": None})
            e["mentions"] += 1
            if one and (not e["one_liner"] or len(one) > len(e["one_liner"])):
                e["one_liner"] = one
            if star and not e["stars"]:
                e["stars"] = star
        # 「dsh-desktop(anywhere-labs)」这种写法自带 owner 提示，用它消歧同名仓库
        for slug, owner in OWNER_HINT.findall(ln):
            slug, owner = slug.lower(), owner.lower()
            if len(slug) < 6 or slug in GENERIC_SLUGS or owner in ("dsh", "npm"):
                continue
            e = entries.setdefault("~" + slug, {"mentions": 0, "one_liner": "", "stars": None})
            e.setdefault("hints", {})
            e["hints"][owner] = e["hints"].get(owner, 0) + 1
    return date, entries, parse_manifest(text)


GENERIC_SLUGS = {"dsh-plugin", "dsh-plugins", "dsh-plugin-", "dsh-harness"}
AMBIG = defaultdict(set)   # slug -> {owner/repo,...} 同名歧义，供人工加 alias


# ---------------------------------------------------------------- 聚合

def scan_deepdives() -> dict:
    """扫描深度调研目录 → key(owner/repo) -> 文档文件名"""
    out = {}
    if not os.path.isdir(DEEPDIVE_DIR):
        return out
    for fn in os.listdir(DEEPDIVE_DIR):
        m = re.match(r"([^_]+)__(.+) 技术调研\.md$", fn)
        if m:
            out[f"{m.group(1)}/{m.group(2)}".lower()] = fn
        m2 = re.match(r"([^_]+)__([^_]+)[ _]?deep dive", fn, re.I)
        if m2:
            out.setdefault(f"{m2.group(1)}/{m2.group(2)}".lower(), fn)
    return out


def resolve2(raw: str, snap_idx, aliases: dict, hints: dict | None = None):
    """归一化 → (key, artifact|None)。key 优先 github 全名，其次注册中心 id。"""
    by_full, by_base, by_id = snap_idx
    if raw in aliases:
        raw = aliases[raw].lower()
        # 人工钉死的映射直接采信，不再二次消歧（目标可能没被 dsh.fish 收录）
        if "/" in raw and not raw.startswith("~"):
            return raw, by_full.get(raw)
    def pack(art):
        fp = full_of(art)
        return (fp or "i:" + art["id"].lower()), art
    if raw.startswith("~"):
        slug = raw[1:]
        if "/" in slug:                      # @scope/pkg → 看 npm 型条目
            art = by_id.get(slug)
            return pack(art) if art else (None, None)
        cands = by_base.get(slug, [])
        owners = {full_of(c) for c in cands}
        if hints:
            want = max(hints.items(), key=lambda kv: kv[1])[0]
            hit = [c for c in cands if (full_of(c) or "").startswith(want + "/")]
            if not hit:
                k = f"{want}/{slug}"
                if k in by_full:
                    hit = [by_full[k]]
            if hit:
                return pack(hit[0])
        if len(owners) == 1 and cands:
            return pack(cands[0])
        if len(owners) > 1:
            AMBIG[slug] |= owners
            return "~" + slug, None          # 同名多仓库且无 owner 提示 → 不猜，留在「未收录」节
        art = by_id.get(slug)
        return pack(art) if art else ("~" + slug, None)
    art = by_full.get(raw)
    if art:
        return raw, art
    base = raw.split("/")[1]
    cands = by_base.get(base, [])
    owners = {full_of(c) for c in cands}
    if len(owners) == 1 and cands:
        return pack(cands[0])
    if len(owners) > 1:
        AMBIG[base] |= owners
        want = raw.split("/")[0]
        hit = [c for c in cands if (full_of(c) or "").startswith(want + "/")]
        if hit:
            return pack(hit[0])
        if ("~" + base) in aliases:            # 该 slug 已人工钉死 → 采信
            k = aliases["~" + base]
            return k, by_full.get(k)
        return "~" + base, None
    art = by_id.get(raw.replace("/", "-"))
    if art:
        return pack(art)
    return raw, None


def build(offline: bool = False) -> dict:
    snap = fetch_snapshot(offline)
    idx = snapshot_indexes(snap)
    by_full = idx[0]
    manual = load_manual()
    aliases = {k.lower(): v.lower() for k, v in manual.get("aliases", {}).items()}
    track_override = manual.get("track", {})
    notes = manual.get("notes", {})
    descs = manual.get("desc", {})

    def lookup_desc(key: str, art) -> str:
        for k in (key, (art or {}).get("id", ""), key.split("/")[-1], "~" + key.split("/")[-1]):
            if k and k in descs:
                return descs[k]
        return ""

    deepdives = scan_deepdives()

    reports = sorted(
        f for f in os.listdir(REPORT_DIR)
        if re.match(r"^\d{4}-\d{2}-\d{2}\.md$", f))
    ledger = {}
    per_day_new = {}
    manifest_rows = []
    for fn in reports:
        date = fn[:10]
        _, entries, manifest = scan_report(os.path.join(REPORT_DIR, fn))
        manifest_rows += [(date, r) for r in manifest]
        for raw, info in entries.items():
            key, art = resolve2(raw, idx, aliases, info.get("hints"))
            if not key:
                continue
            if key.startswith("i:"):
                art_id = key[2:]
                rec = ledger.setdefault(key, {
                    "key": key, "id": art_id, "raw_names": [], "first": date,
                    "last": date, "mentions": 0, "one_liner": "", "track": "",
                    "report_star": None, "in_registry": True})
            else:
                rec = ledger.setdefault(key, {
                    "key": key, "id": (art or {}).get("id", ""), "raw_names": [],
                    "first": date, "last": date, "mentions": 0, "one_liner": "",
                    "track": "", "report_star": None,
                    "in_registry": key in by_full})
                if key.startswith("~"):
                    base = key[1:]
                    cands = idx[1].get(base, [])
                    rec["ambig_n"] = len({full_of(c) for c in cands})
                    rec["ambig_max"] = max([c["stats"]["stars"] for c in cands] or [0])
            rec["first"] = min(rec["first"], date)
            rec["last"] = max(rec["last"], date)
            rec["mentions"] += info["mentions"]
            if raw not in rec["raw_names"]:
                rec["raw_names"].append(raw)
            cand = info["one_liner"]
            if cand and (len(CJK.findall(cand)) > 0 or not rec["one_liner"]):
                if len(cand) > len(rec["one_liner"]) or len(CJK.findall(cand)) > len(CJK.findall(rec["one_liner"])):
                    rec["one_liner"] = cand
            if info["stars"] and date >= rec.get("report_star_date", ""):
                rec["report_star"] = info["stars"]   # 以最近一次日报的快照值为准
                rec["report_star_date"] = date
        for key, rec in ledger.items():
            if rec["first"] == date:
                per_day_new[date] = per_day_new.get(date, 0) + 1

    # 合并：「~slug」未解析且同 base 的已解析条目唯一时并入它
    resolved_by_base = defaultdict(list)
    for k, rec in ledger.items():
        if "/" in k and not k.startswith("~"):
            resolved_by_base[k.split("/")[1]].append(k)
    for k in [k for k in ledger if k.startswith("~")]:
        base = k[1:]
        hits = resolved_by_base.get(base, [])
        if len(hits) == 1:
            tgt = ledger[hits[0]]
            src = ledger.pop(k)
            tgt["mentions"] += src["mentions"]
            tgt["raw_names"] += [r for r in src["raw_names"] if r not in tgt["raw_names"]]
            tgt["first"] = min(tgt["first"], src["first"])
            tgt["last"] = max(tgt["last"], src["last"])
            if src["one_liner"] and len(src["one_liner"]) > len(tgt["one_liner"]):
                tgt["one_liner"] = src["one_liner"]
            if src["report_star"] and not tgt["report_star"]:
                tgt["report_star"] = src["report_star"]
            log(f"[merge] {k} → {hits[0]}")
        elif len(hits) > 1 and ("~" + base) not in aliases:
            ledger[k]["same_name"] = hits[:4]   # 日报里有多个同名仓库，不猜

    # 日报末尾 manifest 块（新格式，精确字段）覆盖一句话 / 赛道，必要时新建条目
    for date, parts in manifest_rows:
        raw = parts[0].lower()
        key, art = resolve2(raw if "/" in raw else "~" + raw, idx, aliases)
        if not key:
            continue
        if key not in ledger:
            ledger[key] = {
                "key": key, "id": (art or {}).get("id", ""), "raw_names": [raw],
                "first": date, "last": date, "mentions": 1, "one_liner": "", "track": "",
                "report_star": None, "in_registry": bool(art),
            }
        rec = ledger[key]
        rec["first"] = min(rec["first"], date)
        rec["last"] = max(rec["last"], date)
        if len(parts) >= 4 and parts[3]:
            rec["one_liner"] = parts[3]
        if len(parts) >= 3 and parts[2]:
            rec["track"] = parts[2]
        if len(parts) >= 2 and parts[1]:
            m = re.match(r"(\d[\d,]*)", parts[1])
            if m and not rec.get("report_star"):
                rec["report_star"] = int(m.group(1).replace(",", ""))

    # 富化 + 归类
    for key, rec in ledger.items():
        art = by_full.get(key) or next(
            (a for a in snap["artifacts"] if a["id"].lower() == rec["id"].lower()), None)
        if not key.startswith("i:") and key in INFRA_KEYS:
            rec["is_infra"] = True
        rec["art"] = art
        if art:
            rec["kind"] = art["kind"]
            rec["grade"] = art["grade"]
            rec["score"] = art["score"]
            rec["velocity"] = art["starVelocity7d"]
            rec["stars"] = art["stats"]["stars"]
            rec["url"] = art.get("sourceUrl", "")
            rec["summary_en"] = art.get("summary", "")
            rec["cats"] = art.get("categories", [])
        else:
            rec["kind"] = ""
            rec["grade"] = ""
            rec["score"] = 0
            rec["velocity"] = 0
            rec["stars"] = rec["report_star"] or 0
            rec["url"] = f"https://github.com/{key}" if "/" in key else ""
            rec["summary_en"] = ""
            rec["cats"] = []
        cands = track_override.get(key)
        rec["track"] = cands or rec["track"] or classify_track(rec)
        rec["status"] = status_of(rec, deepdives)
        if key.startswith("~") and rec.get("ambig_n", 0) > 1:
            rec["status"] = "同名歧义"
        rec["deepdive"] = deepdives.get(key)
        rec["note"] = notes.get(key, "")
        # 一句话描述优先级：人工 desc > 中文（日报原句/注册中心 summary）> 兜底原文
        cand = [lookup_desc(key, rec.get("art")), rec.get("one_liner", ""),
                rec.get("summary_en", "")]
        rec["desc"] = next((c for c in cand if c and len(CJK.findall(c)) >= 4),
                           next((c for c in cand if c), ""))
    # 只按最终条目的首次日期统计，保证「当日新增」求和 == 条目总数
    per_day_new = Counter(rec["first"] for rec in ledger.values())
    if AMBIG:
        log(f"[ambig] {len(AMBIG)} 个 slug 存在同名多仓库（在 manual.json 的 aliases 里钉死）：")
        for slug, cands in sorted(AMBIG.items())[:15]:
            log(f"    {slug} -> {sorted(cands)}")
    other = [e["key"] for e in ledger.values() if not e["track"] or e["track"] == DEFAULT_TRACK]
    if other:
        log(f"[track] 未归类 {len(other)} 条（可在 manual.json 的 track 覆盖）：{other[:20]}")
    return {
        "generated_at": datetime.now(CST).strftime("%Y-%m-%d %H:%M"),
        "snapshot": {
            "generatedAt": snap.get("generatedAt", ""),
            "dataVersion": (snap.get("dataVersion") or "")[:12],
            "artifactCount": snap.get("artifactCount"),
        },
        "registry": {
            "grades": dict(Counter(a["grade"] for a in snap["artifacts"])),
            "kinds": dict(Counter(a["kind"] for a in snap["artifacts"])),
        },
        "entries": list(ledger.values()),
        "per_day_new": per_day_new,
        "reports": reports,
    }


ASCII_KW = re.compile(r"[a-z0-9][a-z0-9 .+\-]*$")


def _kw_hit(kw: str, hay: str) -> bool:
    """ASCII 关键词按词边界匹配，中文按子串匹配。"""
    if ASCII_KW.match(kw):
        return re.search(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", hay) is not None
    return kw in hay


def classify_track(rec: dict) -> str:
    hay = " ".join([
        rec.get("key", "").replace("/", " "), rec.get("id", "").replace("-", " "),
        rec.get("summary_en", ""), rec.get("one_liner", ""),
    ]).lower()
    scores = {}
    for track, kws in TRACK_RULES:
        s = sum(w for kw, w in kws.items() if _kw_hit(kw, hay))
        if s:
            scores[track] = s
    for cat in rec.get("cats", []):
        t = CAT_TRACK.get(cat.lower())
        if t:
            scores[t] = scores.get(t, 0) + 1
    if not scores:
        return DEFAULT_TRACK
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0]


def status_of(rec: dict, deepdives: dict) -> str:
    if rec["key"] in deepdives:
        return "深调研"
    if not rec.get("art"):
        return "未入库"
    if rec["stars"] >= 1000:
        return "头部"
    if rec["velocity"] >= 20:
        return "成长"
    if rec["stars"] >= 10:
        return "活跃"
    return "观察"


# ---------------------------------------------------------------- 渲染

def fmt_stars(n: int) -> str:
    if not n:
        return "—"
    return f"{n:,}"


def render(ledger: dict) -> str:
    ents = ledger["entries"]
    inreg = [e for e in ents if e.get("art")]
    notin = [e for e in ents if not e.get("art")]
    alle = sorted(ents, key=lambda e: (-e["stars"], -e["mentions"], e["key"]))
    now = ledger["generated_at"]
    snap = ledger["snapshot"]
    reg = ledger["registry"]
    g = reg.get("grades", {})
    k = reg.get("kinds", {})
    total_reg = snap.get("artifactCount") or sum(g.values())

    track_cnt = Counter(e["track"] for e in inreg)
    lines: list[str] = []
    A = lines.append
    A("---")
    A("type: moc")
    A("title: dsh 插件总表（历史全量台账）")
    A("created: 2026-09-14")
    A(f"updated: {now[:10]}")
    A("tags: [索引, DeepSeek, Harness, 插件, 台账, dsh]")
    A("---")
    A("")
    A("# dsh 插件总表（历史全量台账）")
    A("")
    A(f"> 本表由脚本 `~/.hermes/skills/research/dsh-plugin-daily/scripts/dsh_ledger.py` 生成，"
      f"最近生成 {now}（CST）。")
    A("> 数据来源：本目录 22+ 份日报（2026-08-20 起）逐行解析 + dsh.fish 注册中心快照"
      f"（`generatedAt` {snap.get('generatedAt','')}，`dataVersion` `{snap.get('dataVersion','')}`，"
      f"共 {total_reg:,} 条）。")
    A("> **每日日报写完后再跑一次 `python dsh_ledger.py update`，当天内容自动并入本表**（见 skill `dsh-plugin-daily`）。")
    A("")
    A("## 一、总览")
    A("")
    A("| 指标 | 数值 |")
    A("|:--|:--|")
    A(f"| 本表收录条目（日报提及过） | **{len(ents):,}** |")
    A(f"| 其中已对齐注册中心 | {len(inreg):,} |")
    A(f"| 其中注册中心未收录（可能已改名/私有/npm 发布） | {len(notin):,} |")
    A(f"| 已出深度调研文档 | **{sum(1 for e in ents if e['deepdive'])}** |")
    A(f"| 头部（≥1,000★） | {sum(1 for e in inreg if e['stars'] >= 1000)} |")
    A(f"| 成长中（7 日星速 ≥20） | {sum(1 for e in inreg if e['velocity'] >= 20)} |")
    A(f"| 注册中心总量 / 评分分布 | {total_reg:,} 条 · S {g.get('S',0)} / A {g.get('A',0)} / "
      f"B {g.get('B',0):,} / C {g.get('C',0):,} |")
    A(f"| 注册中心类型分布 | bundle {k.get('bundle',0):,} / skill {k.get('skill',0)} / "
      f"agent-preset {k.get('agent-preset',0)} / profile {k.get('profile',0)} |")
    A("")
    A("## 二、赛道分布（本表条目，[推断] 自动归类）")
    A("")
    A("| 赛道 | 条目数 | 头部代表 |")
    A("|:--|--:|:--|")
    for track, cnt in track_cnt.most_common():
        tops = [e for e in inreg if e["track"] == track][:3]
        rep = "、".join(f"{short_name(e)}（{fmt_stars(e['stars'])}★）" for e in tops if e["stars"])
        A(f"| {track} | {cnt} | {rep} |")
    A("")
    A("## 三、主台账（全量，按星数倒序）")
    A("")
    A("一个表装完：日报提到过的都在这里。`状态` 为 `未入库` 的表示 dsh.fish 注册中心里查不到"
      "（可能已改名、私有、只发 npm），其星数取自日报当时的快照值，可能已过时。")
    A("")
    A("| 插件 | 类型 | 星数 | 7日星速 | 评级 | 赛道 | 首次 | 最近 | 状态 | 一句话 |")
    A("|:--|:--|--:|--:|:-:|:--|:--|:--|:--|:--|")
    for e in alle:
        A(f"| {link_name(e)} | {e['kind'] or '—'} | {fmt_stars(e['stars'])} | "
          f"{e['velocity'] or '—'} | {e['grade'] or '—'} | {e['track']} | {e['first'][5:]} | "
          f"{e['last'][5:]} | {e['status']} | {clean_cell(e['desc'])} |")
    A("")
    A("## 四、已出深度调研文档（Tier 1/2）")
    A("")
    A("| 项目 | 星数 | 文档 |")
    A("|:--|--:|:--|")
    for e in sorted([x for x in ents if x["deepdive"]], key=lambda x: -x["stars"]):
        doc = e["deepdive"][:-3]
        A(f"| {link_name(e)} | {fmt_stars(e['stars']) or '—'} | "
          f"[[调研分析/DeepSeek Harness/深度调研/{doc}\\|{doc}]] |")
    A("")
    A("## 五、生态基建与跨生态参考（不算插件，雷达持续跟踪）")
    A("")
    A("| 项目 | 星数 | 说明 |")
    A("|:--|--:|:--|")
    infra = [e for e in ents if e.get("is_infra")]
    for e in sorted(infra, key=lambda x: -x["stars"]):
        desc = INFRA_KEYS.get(e["key"], e["one_liner"])
        A(f"| {link_name(e)} | {fmt_stars(e['stars']) or '—'} | {clean_cell(desc)} |")
    A("")
    A("## 六、注册中心未收录的条目（名单速览）")
    A("")
    A("共 %d 条，明细见主台账（状态列 `未入库`）。多为已改名、未提交 dsh.fish、或只发 npm 的插件。"
      % len(notin))
    A("")
    A(" ".join(f"`{e['id'] or e['key']}`" for e in notin))
    A("")
    A("## 七、更新记录（每日并入情况）")
    A("")
    A("| 日期 | 当日首次进表条目 | 累计条目 | 来源日报 |")
    A("|:--|--:|--:|:--|")
    cum = 0
    for fn in ledger["reports"]:
        d = fn[:10]
        new = ledger["per_day_new"].get(d, 0)
        cum += new
        A(f"| {d} | {new} | {cum} | "
          f"[[调研分析/DeepSeek Harness/dsh插件每日雷达/{d}\\|{d} 日报]] |")
    A("")
    A("## 字段说明")
    A("")
    A(FIELD_DOC.strip())
    A("")
    A("## 维护")
    A("")
    A("```bash")
    A("# 每日：日报写完后并入总表（自动拉最新 snapshot）")
    A("python ~/.hermes/skills/research/dsh-plugin-daily/scripts/dsh_ledger.py update")
    A("# 全量重建 / 只看统计 / 离线")
    A("python ~/.hermes/skills/research/dsh-plugin-daily/scripts/dsh_ledger.py rebuild")
    A("python ~/.hermes/skills/research/dsh-plugin-daily/scripts/dsh_ledger.py report")
    A("python ~/.hermes/skills/research/dsh-plugin-daily/scripts/dsh_ledger.py update --offline")
    A("```")
    A("")
    A("别名/赛道覆盖/备注写在 `data/manual.json`（脚本不覆盖）：")
    A("`aliases` 归一化（改名、同名歧义）、`track` 覆盖赛道、`notes` 人工备注。")
    A("")
    A("## 关联")
    A("")
    A("- [[调研分析/DeepSeek Harness/dsh插件每日雷达/00-索引|📡 dsh 插件每日雷达索引]]")
    A("- [[调研分析/DeepSeek Harness/深度调研/00-索引|📕 深度调研索引]]")
    A("- [[调研分析/DeepSeek Harness/00-索引|DSH 主索引]]")
    A("")
    return "\n".join(lines) + "\n"


def short_name(e: dict) -> str:
    n = e.get("id") or e["key"]
    return n if len(n) <= 42 else n[:41] + "…"


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def link_name(e: dict) -> str:
    """显示名 = 注册中心 id（无则 owner/repo）；真正对不上时补注仓库/别名。"""
    n = short_name(e)
    url = e.get("url") or ""
    n_norm = _norm_key(e.get("id") or e["key"])
    extras = []
    repo = e["key"].split("/")[-1] if "/" in e["key"] else ""
    if e.get("ambig_n", 0) > 1:
        extras.append(f"注册中心同名 {e['ambig_n']} 个，最大 {e['ambig_max']}★")
    if e.get("same_name"):
        extras.append("同名候选 " + "、".join(x.split("/")[-1] for x in e["same_name"]))
    if repo and _norm_key(repo) not in n_norm:
        extras.append(f"仓库 {repo}")
    for raw in e["raw_names"]:
        r = raw[1:] if raw.startswith("~") else raw.split("/")[-1]
        if r and _norm_key(r) not in n_norm and _norm_key(r) not in _norm_key(repo):
            if r not in [x.split()[-1] for x in extras]:
                extras.append(f"别名 {r}")
    txt = n + ("（" + "、".join(extras[:2]) + "）" if extras else "")
    return f"[{txt}]({url})" if url else txt


def clean_cell(s: str) -> str:
    s = (s or "").replace("|", "／").replace("\n", " ")
    s = re.sub(r"\[源[^\]]*\]", "", s)          # 去掉 [源: api] 之类尾部标注
    s = s.replace("🆕", "").replace("⭐", "").replace("★", "")
    s = re.sub(r"\*{1,}", "", s)
    s = re.sub(r"^[\s:：、。·\-（）()]+", "", s)
    s = re.sub(r"^新进\s*", "", s)
    s = re.sub(r"^[（(]?(改名|更名|旧名)[)）]?\s*", "", s)
    s = re.sub(r"[\s:：、]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 90:                      # 长句只留第一句，保持「一句话」体例
        cut = max(s.find("。"), s.find("；"))
        if 20 <= cut <= 140:
            s = s[:cut + 1]
        elif len(s) > 120:
            s = s[:118].rstrip() + "…"
    return s


def check(ledger: dict, since: str | None = None) -> int:
    """质量门禁：返回问题数（0 = 全过）。

    门禁项：
    1. 每条都要有中文「干啥的」描述（无 = 要么日报没写清，要么 desc 没补）
    2. 赛道不能落在「其他」
    3. 同名歧义条目数量（提示，不算失败）
    `since` 只检查首次出现日期 >= since 的条目（当天新增），用于日报跑完后自查。
    """
    ents = ledger["entries"]
    if since:
        ents = [e for e in ents if e["first"] >= since]
    no_desc = [e for e in ents if len(CJK.findall(e.get("desc") or "")) < 4]
    no_track = [e for e in ents if not e.get("track") or e.get("track") == DEFAULT_TRACK]
    ambig = [e for e in ents if e.get("status") == "同名歧义"]
    scope = f"（自 {since} 起新增 {len(ents)} 条）" if since else "（全表 %d 条）" % len(ents)
    log(f"[check] 范围 {scope}")
    if no_desc:
        log(f"[check] ✗ {len(no_desc)} 条缺中文描述 → 补进 data/manual.json 的 desc（key/id/仓库短名都能命中）：")
        for e in no_desc[:40]:
            log(f"        {e['key']}  {e['stars']}★  EN={(e.get('summary_en') or '')[:70]!r}")
    else:
        log("[check] ✓ 中文描述齐全")
    if no_track:
        log(f"[check] ✗ {len(no_track)} 条赛道未归类 → 补进 data/manual.json 的 track：")
        for e in no_track[:20]:
            log(f"        {e['key']}")
    else:
        log("[check] ✓ 赛道全部归类")
    if ambig:
        log(f"[check] ⚠ {len(ambig)} 条同名歧义（不阻塞，确认后可用 aliases 钉死）：{', '.join(e['key'] for e in ambig)}")
    bad = len(no_desc) + len(no_track)
    log(f"[check] {'通过' if bad == 0 else '未通过，问题 %d 项' % bad}")
    return bad


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["rebuild", "update", "report", "check"])
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--dry", action="store_true", help="只打印不写文件")
    ap.add_argument("--since", help="check 模式：只检查此日期（含）之后首次进表的条目，如 2026-09-15")
    args = ap.parse_args()

    ledger = build(offline=args.offline)
    os.makedirs(DATA, exist_ok=True)
    md = render(ledger)

    ents = ledger["entries"]
    inreg = [e for e in ents if e.get("art")]
    log(f"[ledger] 条目 {len(ents)}（入库 {len(inreg)}）| 快照 {ledger['snapshot']['artifactCount']}")
    if args.mode == "check":
        sys.exit(1 if check(ledger, args.since) else 0)
    if args.mode != "report" and not args.dry:
        with open(LEDGER_JSON, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in ledger.items() if k != "entries"} |
                      {"entries": [{kk: vv for kk, vv in e.items() if kk not in ("art",)} for e in ents]},
                      f, ensure_ascii=False, indent=1)
        with open(OUT_MD, "w", encoding="utf-8") as f:
            f.write(md)
        log(f"[ledger] 写入 {OUT_MD}（{len(md.encode('utf-8'))} bytes）")
    else:
        print(md)


if __name__ == "__main__":
    main()
