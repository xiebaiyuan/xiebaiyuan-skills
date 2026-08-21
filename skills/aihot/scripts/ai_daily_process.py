#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 每日要闻处理脚本 v2：修复 backlink 越界/乱匹配、AIHOT 同源去重、重点精选逻辑"""
import json, re, urllib.request, datetime, os, glob, difflib

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
HN_KEYWORDS = ["gpt", "claude", "llm", "model", "agent", "openai", "anthropic",
               "deepseek", "gemini", "mistral", "llama", "diffusion", "vllm",
               "ollama", "huggingface", "mcp", "rag", "token", "ai ", " ai",
               "neural", "machine learning", "transformer", "inference", "gpu",
               "nvidia", "ais", "agi", "copilot", "chatbot", "suno", "midjourney",
               "stable diffusion", "robot", "autonomous"]

def is_ai(title):
    t = (title or "").lower()
    return any(k in t for k in HN_KEYWORDS)

hn_items = []
try:
    with open("/tmp/hn_ids.json") as f:
        hn_ids = json.load(f)[:50]
    got = 0
    for hid in hn_ids:
        try:
            item = json.loads(fetch(f"https://hacker-news.firebaseio.com/v0/item/{hid}.json", timeout=15))
            if item and item.get("type") == "story" and item.get("title") and is_ai(item.get("title", "")):
                hn_items.append({"title": item["title"], "url": item.get("url", f"https://news.ycombinator.com/item?id={hid}"),
                                 "score": item.get("score", 0)})
            got += 1
        except Exception:
            continue
    print(f"HN fetched {got}/50, AI-related {len(hn_items)}")
except Exception as e:
    print(f"HN READ ERR: {e}")
hn_items.sort(key=lambda x: -x["score"])

# ---------- 3. 合并去重 ----------
STOP_CN = {"一个", "一份", "如何", "今天", "正式", "发布", "推出", "宣布", "我们", "关于", "使用", "通过", "进行", "实现", "以及", "用于", "提供", "旗下", "公司", "平台"}
STOP_EN = {"the", "and", "for", "with", "from", "that", "this", "you", "your", "his", "her", "its", "are", "was", "were", "has", "had", "not", "but", "can", "will", "into", "over", "after", "under", "what", "when", "openai", "hacker", "news", "blog", "simple", "pricing", "fix", "best", "brings", "allowed", "model", "your", "their", "there", "would", "could", "should"}

def norm(s):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (s or "").lower())[:40]

def norm_title(t):
    t = (t or "").lower()
    t = re.sub(r"show hn|launch hn|ask hn", "", t)
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", t)[:40]

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

# AIHOT 内部同源去重（同一新闻多URL：如 X 帖 + 官方 blog）
def distinct_tokens(t):
    return set(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9\-\.]{5,}", t))

def same_story(a, b):
    r = difflib.SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()
    if r >= 0.62:
        return True
    if r >= 0.30:
        shared = distinct_tokens(a) & distinct_tokens(b)
        if shared:
            return True
    return False

final_merged = []
for m in merged:
    dup = None
    for fm in final_merged:
        if same_story(m["title"], fm["title"]):
            dup = fm
            break
    if dup:
        dup["alt_urls"].append(m["url"])
        if m["summary"] and m["summary"] not in dup["summary"]:
            # 同源合并：保留更详细的 summary，避免同一新闻两段重复
            if len(m["summary"]) > len(dup["summary"]) * 1.15:
                dup["summary"] = m["summary"]
            elif len(dup["summary"]) > len(m["summary"]) * 1.15:
                pass  # 已保留更详细的一条
            else:
                dup["summary"] += " " + m["summary"]
    else:
        final_merged.append(m)
merged = final_merged

for h in hn_items:
    key = norm_title(h["title"])
    matched = None
    for m in merged:
        if norm_title(m["title"]) == key or (m["url"] and h["url"] and m["url"].rstrip("/") == h["url"].rstrip("/")):
            matched = m
            break
    if matched:
        matched["hn"], matched["hn_score"] = True, h["score"]
    elif key not in seen:
        seen.add(key)
        merged.append({"title": h["title"], "url": h["url"], "src": "Hacker News", "category": "hn",
                       "summary": "", "aihot": False, "hn": True, "hn_score": h["score"], "alt_urls": []})

# ---------- 4. 关联 vault 调研（Python glob + realpath 越界防护） ----------
VAULT = os.path.expanduser("~/AI_DOC")
VAULT_REAL = os.path.realpath(VAULT)
# 排除目录：每日要闻自身、技术调研子目录
EXCLUDE_DIRS = ("调研分析/每日要闻", "调研分析/技术调研", "调研分析/产品对比")

def find_entity_links(title):
    cands = []
    # 英文 token 长度 >=5，避免 "cut"→OpenCut、"gpt"→Humanoid-GPT 类子串噪音
    for w in re.findall(r"[A-Za-z][A-Za-z0-9\-\.]{4,}", title):
        wl = w.lower()
        if len(w) >= 5 and wl not in STOP_EN and not wl.startswith("http") and wl not in ("com", "www", "html"):
            cands.append(w)
    for w in re.findall(r"[\u4e00-\u9fff]{2,6}", title):
        if w not in STOP_CN:
            cands.append(w)
    found = []
    seen_link = set()
    for c in cands:
        for root in (f"{VAULT}/wiki/entities", f"{VAULT}/调研分析"):
            for p in glob.glob(f"{root}/*{c}*"):
                p_real = os.path.realpath(p)
                if not p_real.startswith(VAULT_REAL + "/"):
                    continue
                rel = os.path.relpath(p, VAULT).replace(".md", "")
                if any(rel.startswith(d) for d in EXCLUDE_DIRS):
                    continue
                if rel.startswith("调研分析/") and rel.count("/") > 1:
                    continue
                if not p.endswith(".md"):
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
# 优先级：AIHOT 行业重磅(关键词命中) → 双源 → HN 高分 → AIHOT 其余
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
L.append(f"> 覆盖窗口：UTC {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')}（北京 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}）")
L.append(f"> 数据源：AI HOT 精选 {len(aihot_items)} 条 + HN Top50 中 AI 相关 {len(hn_items)} 条 → 去重合并 **{len(merged)} 条**")
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
L.append("- HN 条目仅按标题关键词过滤 + 分数排序，未人工核读")
L.append("- 数字不约写，缩写不猜测；所有 URL 为原始出处链接")
L.append("")

out = "\n".join(L)
with open("/tmp/ai_brief.md", "w") as f:
    f.write(out)

print("=" * 60)
print(f"AIHOT raw {len(aihot_items)} -> after dedupe merged {len(merged)} | HN AI {len(hn_items)} | backlink hits {sum(1 for v in backlinks.values() if v)}")
print("----- backlink debug -----")
for t, v in backlinks.items():
    if v:
        print(f"  {t[:44]} -> {v}")
print("--------------------------")
print(f"Brief chars: {len(out)}")