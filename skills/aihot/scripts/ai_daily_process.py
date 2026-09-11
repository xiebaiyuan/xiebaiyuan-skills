#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 每日要闻处理脚本 v3（2026-09-11）

v2 → v3 修复：
  1) 同源合并过激：v2 的「ratio≥0.30 且共享任意 ≥6 字符 token」会把只共享品牌名
     （DeepSeek/Anthropic/OpenAI）的不同新闻合并（如「Anthropic 指控…DeepSeek 蒸馏」
     +「DeepSeek 发布 V4.1-Flash」）。v3 只认 ratio≥0.55，且品牌名/通用词不参与判定。
  2) 标题与摘要错位（最严重）：v2 合并时保留先出现条目的 title，却可能把后一条更长的
     summary 换进来，产出「Anthropic 蒸馏攻击」配「DeepSeek V4.1-Flash 摘要」这种错配。
     v3 改为「整条代表项替换」：title/url/summary/category 永远取自同一条目。
  3) HN↔AIHOT 双源识别：v2 只比对标题全等/URL 全等，漏掉 HN「DeepSeek v4.1 Flash」
     ↔ AIHOT「…DeepSeek-V4.1-Flash…」这类同源。v3 增加「共享非通用词 token」判定。
  4) HN 关键词误命中：v2 的 'cognition'/'trust'/'ais' 之类子串会命中
     Hofstadter 认知科学视频、"untrusted"、甚至无关帖子。v3 用词边界匹配 + 去噪词表。

用法：python3 ai_daily_process.py [输出路径，默认 /tmp/ai_brief.md]
前置：/tmp/aihot.json（AI HOT API 落盘）、/tmp/hn_ids.json（HN topstories 落盘）
"""
import json, re, sys, os, glob, difflib, datetime, urllib.request

OUT_PATH = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ai_brief.md"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------- 1. AI HOT ----------
aihot_items = []
try:
    with open("/tmp/aihot.json") as f:
        aihot_items = json.load(f).get("items", [])
except Exception as e:
    print(f"AIHOT READ ERR: {e}")

# ---------- 2. HN ----------
# 短词用词边界匹配，避免 "ai"→"Deathray"、"trust"→"untrusted"、"cognition"→认知科学视频
HN_KEYWORDS = ["gpt", "claude", "llm", "model", "agent", "openai", "anthropic",
               "deepseek", "gemini", "mistral", "llama", "diffusion", "vllm",
               "ollama", "huggingface", "mcp", "rag", "token", "neural",
               "machine learning", "transformer", "inference", "gpu", "nvidia",
               "copilot", "chatbot", "suno", "midjourney", "stable diffusion",
               "llm", "codex", "kagi", "multimatte", "pretraining", "fine-tuning",
               "trust", "unpublished math"]
HN_STOP_NON_AI = ["deathray", "untrusted"]  # 命中即判定为误命中（安全/系统类话题）


def is_ai(title):
    t = (title or "").lower()
    if any(s in t for s in HN_STOP_NON_AI):
        return False
    for k in HN_KEYWORDS:
        if len(k) <= 4:
            if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t):
                return True
        elif k in t:
            return True
    return False


hn_items = []
try:
    with open("/tmp/hn_ids.json") as f:
        hn_ids = json.load(f)[:50]
    got = 0
    for hid in hn_ids:
        try:
            item = json.loads(fetch(f"https://hacker-news.firebaseio.com/v0/item/{hid}.json", timeout=15))
            if item and item.get("type") == "story" and is_ai(item.get("title", "")):
                hn_items.append({"title": item["title"],
                                 "url": item.get("url", f"https://news.ycombinator.com/item?id={hid}"),
                                 "hn_url": f"https://news.ycombinator.com/item?id={hid}",
                                 "score": item.get("score", 0) or 0})
            got += 1
        except Exception:
            continue
    print(f"HN fetched {got}/50, AI-related {len(hn_items)}")
    for h in hn_items:
        print(f"   HN {h['score']:>4} | {h['title'][:80]}")
except Exception as e:
    print(f"HN READ ERR: {e}")
hn_items.sort(key=lambda x: -x["score"])

# ---------- 3. 合并去重 ----------
STOP_CN = {"一个", "一份", "如何", "今天", "正式", "发布", "推出", "宣布", "我们", "关于", "使用",
           "通过", "进行", "实现", "以及", "用于", "提供", "旗下", "公司", "平台", "支持", "上线",
           "全新", "数据", "能力", "模型", "功能", "版本", "计划", "报告", "更新"}
STOP_EN = {"the", "and", "for", "with", "from", "that", "this", "you", "your", "his", "her", "its",
           "are", "was", "were", "has", "had", "not", "but", "can", "will", "into", "over", "after",
           "under", "what", "when", "openai", "hacker", "news", "blog", "simple", "pricing", "fix",
           "best", "brings", "allowed", "model", "their", "there", "would", "could", "should",
           "launches", "launch", "new", "show", "ask", "introducing", "release", "releases",
           "announces", "announcing", "achieves", "rivaling", "using", "based"}
# 品牌/机构/产品名：出现在标题里不代表同一件事，绝不能作为「同源」依据
BRAND_TOKENS = {"openai", "anthropic", "deepseek", "google", "meta", "microsoft", "nvidia", "apple",
                "amazon", "alibaba", "moonshot", "minimax", "stepfun", "tencent", "baidu", "xai",
                "mistral", "qwen", "gemini", "claude", "llama", "grok", "suno", "cursor", "cognition",
                "huggingface", "github", "cloudflare", "vercel", "shopify", "discord", "slack",
                "windows", "linux", "macos", "android", "chrome", "firefox", "pytorch", "tensorflow"}


def norm_title(t):
    t = (t or "").lower()
    t = re.sub(r"show hn|launch hn|ask hn", "", t)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", t)[:40]


def strip_brand(t):
    """去掉品牌名与通用发布词，只留下「这件事」的特征词，用于同源比对"""
    t = (t or "").lower()
    for b in list(BRAND_TOKENS) + list(STOP_EN):
        t = re.sub(r"(?<![a-z])" + re.escape(b) + r"(?![a-z])", " ", t)
    for c in STOP_CN:
        t = t.replace(c, " ")
    return t


def _tokens(t):
    """标题特征 token 集：
    - 拆开连字符/点号/下划线，去掉品牌与通用词；
    - 保留长度 ≥4 的词，或「含数字的 ≥2 字符」片段（v4、swe2 这类版本号）；
    - 若复合词去掉品牌后仍有 ≥2 段，再合并成复合 token（deepseek-v4.1-flash → v4-1-flash），
      这样不同写法（DeepSeek-V4.1-Flash / V4.1-Flash）能对上，而品牌名本身不算依据。
    """
    out = set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-\._]{1,}", t or ""):
        parts = []
        for part in re.split(r"[\-\._]", w):
            pl = part.lower()
            if not pl:
                continue
            if pl in STOP_EN or pl in BRAND_TOKENS:
                continue
            if len(pl) >= 4 or (len(pl) >= 2 and any(ch.isdigit() for ch in pl)):
                parts.append(pl)
                out.add(pl)
        if len(parts) >= 2:
            out.add("-".join(parts))
    return out


def distinct_tokens(t):
    """保持旧名兼容：HN 匹配、同源判定都用这一套 token"""
    return _tokens(t)


STRONG = re.compile(r"[0-9]")  # 含数字/版本号的 token 视为强信号


def same_story(a, b, ca=None, cb=None):
    """同一件事判定（v3.1）：
    - 不同分类（如 ai-models 公告 vs tip 解读）默认不合并，除非标题几乎一致（ratio ≥ 0.75）
    - 共享「含数字的复合 token」（v4-1-flash / agents-api）→ 合并
    - 共享 ≥2 个特征 token 且标题 ratio ≥ 0.35 → 合并
    - 标题（去掉品牌与发布类词后）ratio ≥ 0.55 → 合并
    """
    ta, tb = _tokens(a), _tokens(b)
    shared = ta & tb
    if ca and cb and ca != cb:
        return difflib.SequenceMatcher(None, norm_title(a), norm_title(b)).ratio() >= 0.75
    if shared and any(("-" in t or STRONG.search(t)) for t in shared):
        return True
    r = difflib.SequenceMatcher(None, norm_title(strip_brand(a)), norm_title(strip_brand(b))).ratio()
    if len(shared) >= 2 and r >= 0.35:
        return True
    return r >= 0.55


merged = []
seen = set()
for it in aihot_items:
    title = it.get("title") or it.get("title_en") or ""
    if not title or "show hn" in title.lower() or "ask hn" in title.lower():
        continue
    key = norm_title(title)
    if key in seen:
        continue
    seen.add(key)
    merged.append({"title": title, "url": it.get("url", ""), "src": it.get("source", ""),
                   "category": it.get("category", "industry"), "summary": it.get("summary", ""),
                   "aihot": True, "hn": False, "hn_score": 0, "alt_urls": []})

# AIHOT 内部同源去重：代表项整条替换，绝不做 title/summary 交叉拼接
final_merged = []
for m in merged:
    dup = None
    for fm in final_merged:
        if same_story(m["title"], fm["title"], m["category"], fm["category"]):
            dup = fm
            break
    if dup:
        if m["url"] and m["url"] != dup["url"]:
            dup["alt_urls"].append(m["url"])
        if len(m["summary"] or "") > len(dup["summary"] or ""):
            # 代表项换成信息更全的那条：title/url/summary/category 一起换
            old_url = dup["url"]
            dup.update({"title": m["title"], "url": m["url"], "summary": m["summary"],
                        "src": m["src"], "category": m["category"]})
            if old_url and old_url not in dup["alt_urls"]:
                dup["alt_urls"].insert(0, old_url)
    else:
        final_merged.append(m)
merged = final_merged

# HN ↔ AIHOT 双源识别：标题全等 / URL 全等 / 共享特征 token
for h in hn_items:
    key = norm_title(h["title"])
    h_tokens = distinct_tokens(h["title"])
    matched = None
    for m in merged:
        m_url = (m["url"] or "").rstrip("/").rstrip("#")
        h_url = (h["url"] or "").rstrip("/").rstrip("#")
        if key == norm_title(m["title"]) or (m_url and m_url == h_url):
            matched = m
            break
        shared = h_tokens & distinct_tokens(m["title"])
        if shared and any(("-" in t or STRONG.search(t) or len(t) >= 5) for t in shared):
            matched = m
            break
    if matched:
        matched["hn"] = True
        matched["hn_score"] = max(matched["hn_score"], h["score"])
        if h["url"] and h["url"] != matched["url"] and h["url"] not in matched["alt_urls"]:
            matched["alt_urls"].append(h["url"])
    elif key not in seen:
        seen.add(key)
        merged.append({"title": h["title"], "url": h["url"], "src": "Hacker News", "category": "hn",
                       "summary": "", "aihot": False, "hn": True, "hn_score": h["score"], "alt_urls": []})

# ---------- 4. 关联 vault 调研 ----------
VAULT = os.path.expanduser("~/AI_DOC")
VAULT_REAL = os.path.realpath(VAULT)
EXCLUDE_DIRS = ("调研分析/每日要闻", "调研分析/技术调研", "调研分析/产品对比")


def find_entity_links(title):
    cands = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-\.]{4,}", title):
        wl = w.lower()
        if len(w) >= 5 and wl not in STOP_EN and not wl.startswith("http") and wl not in ("com", "www", "html"):
            cands.append(w)
    for w in re.findall(r"[\u4e00-\u9fff]{2,6}", title):
        if w not in STOP_CN:
            cands.append(w)
    found, seen_link = [], set()
    for c in cands:
        for root in (f"{VAULT}/wiki/entities", f"{VAULT}/调研分析"):
            for p in glob.glob(f"{root}/*{c}*"):
                p_real = os.path.realpath(p)
                if not p_real.startswith(VAULT_REAL + "/"):
                    continue
                if not p.endswith(".md"):
                    continue
                rel = os.path.relpath(p, VAULT).replace(".md", "")
                if any(rel.startswith(d) for d in EXCLUDE_DIRS):
                    continue
                if rel.startswith("调研分析/") and rel.count("/") > 1:
                    continue
                label = os.path.basename(rel)[:24]
                link = f"[[{rel}|📄 {label}]]"
                if link not in seen_link:
                    seen_link.add(link)
                    found.append(link)
        if len(found) >= 2:
            break
    return found[:2]


backlinks = {m["title"]: find_entity_links(m["title"]) for m in merged}

# ---------- 5. 昨日简报 ----------
def get_yesterday():
    y = datetime.date.today() - datetime.timedelta(days=1)
    p = f"{VAULT}/调研分析/每日要闻/{y.isoformat()}-AI要闻.md"
    if os.path.exists(p):
        try:
            with open(p) as f:
                return f.read()
        except Exception:
            return ""
    return ""


yesterday = get_yesterday()
yesterday_titles = set(re.findall(r"^\d+\.\s*\[([^\]]+)\]", yesterday, re.M))

# ---------- 6. 重点精选 ----------
def key_prio(m):
    t = m["title"]
    if m["aihot"] and any(k in t for k in ["NVIDIA", "OpenAI", "黄仁勋", "宇树", "Anthropic", "Google", "GPT"]):
        return 0
    if m["hn"] and m["aihot"]:
        return 1
    if m["hn"] and m["hn_score"] >= 300:
        return 2
    if m["hn"] and m["hn_score"] >= 200:
        return 3
    return 4


key_items = sorted([m for m in merged if key_prio(m) < 4], key=lambda m: (key_prio(m), -m["hn_score"]))[:5]

# ---------- 7. 输出 ----------
CAT_LABEL = [("ai-models", "🤖 模型发布"), ("ai-products", "📦 产品发布/更新"),
             ("industry", "🏭 行业动态"), ("paper", "📄 论文研究"),
             ("tip", "💡 技巧与观点"), ("hn", "💬 Hacker News 热帖")]


def src_tag(m):
    parts = ["AI HOT"] if m["aihot"] else []
    if m["hn"]:
        parts.append(f"HN（{m['hn_score']} 分）")
    return " + ".join(parts)


L = []
L.append("---")
L.append(f"date: {datetime.date.today().isoformat()}")
L.append("tags: [AI要闻, 日报]")
L.append("type: daily-news")
L.append("---")
L.append("")
L.append(f"# AI 每日要闻 {datetime.date.today().isoformat()}")
L.append("")
L.append(f"> 覆盖窗口：UTC {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')}（北京 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}）前推 24 小时")
L.append(f"> 数据源：AI HOT 精选 {len(aihot_items)} 条 + HN Top50 中关键词命中 {len(hn_items)} 条 → 去重合并 **{len(merged)} 条**")
if not aihot_items:
    L.append("> ⚠️ AI HOT 今日无数据（API 可能未更新），以下仅 HN 来源")
L.append("")


def fmt_entry(m, n):
    out = [f"{n}. [{m['title']}]({m['url']}) 🆕 — {src_tag(m)}"]
    if m["summary"]:
        out.append(f"   {m['summary']}")
    if m["alt_urls"]:
        out.append(f"   同源链接：{'、'.join(m['alt_urls'])}")
    if m["title"] in yesterday_titles:
        out.append("   > 📌 与昨日简报重复，新闻处于持续发酵期")
    for bl in backlinks.get(m["title"], []):
        out.append(f"   · {bl}")
    return out


n = 0
L.append("## 🔥 今日重点")
L.append("")
for m in merged:
    if m in key_items:
        n += 1
        L.extend(fmt_entry(m, n))
        L.append("")
L.append("")

rest = [m for m in merged if m not in key_items]
for cat, header in CAT_LABEL:
    group = [m for m in rest if m["category"] == cat]
    if not group:
        continue
    L.append(f"## {header}")
    L.append("")
    for m in group:
        n += 1
        L.extend(fmt_entry(m, n))
        L.append("")
    L.append("")

L.append("---")
L.append("")
L.append("## 信源说明")
L.append("")
L.append("- 条目 summary 为 AI HOT 平台精选摘要原文（平台对原文的转述，细节以原文为准）")
L.append("- 无 summary 的条目为标题概括，未经全文核读")
L.append("- HN 条目仅按标题关键词过滤 + 分数排序，未人工核读；词边界匹配后仍可能有误命中，落盘前人工扫一遍")
L.append("- 数字不约写，缩写不猜测；所有 URL 为原始出处链接")
L.append("")

out = "\n".join(L)
with open(OUT_PATH, "w") as f:
    f.write(out)

print("=" * 60)
print(f"AIHOT raw {len(aihot_items)} + HN AI {len(hn_items)} -> merged {len(merged)} entries")
print("----- backlink debug（人工修剪误链）-----")
for t, v in backlinks.items():
    if v:
        print(f"  {t[:44]} -> {v}")
print("--------------------------")
print(f"Brief chars: {len(out)} -> {OUT_PATH}")
