# -*- coding: utf-8 -*-
"""Cross-period dedupe for a new briefing: compare against the previous N briefings.

WHY: the same story reappears on HN under a different domain/author, so keyword and
URL dedupe against the *current* window both miss it. Comparing HN item ids and
URL host+path against the last few briefing files catches them (2026-09-21 lesson,
measured 46/68 hits on 2026-09-24). Never rely on re-reading titles by hand.

Usage:
  python3 brief_xref_prev.py <today YYYY-MM-DD> [--prev 3] [--ids "49764791,49792730"]

Inputs:
  /tmp/hn_items.json  detail payloads for the Top-N scan (hn_fetch_fast.py writes it)
  /tmp/aihot.json     AI HOT pull (aihot_pull.py writes it)
  --ids               HN ids you consider AI-side this period; omit to use /tmp/hn_ai.json
                      (the keyword-filtered hits). Manual picks matter: the keyword table
                      misses titles without AI words, and those are often the top stories.

Output: one line per item -> CROSS (already reported, which issue) or NEW (score/comments).
"""
import argparse
import json
import os
import re
from urllib.parse import urlparse

VAULT = os.path.expanduser("~/AI_DOC/调研分析/每日要闻")

ap = argparse.ArgumentParser()
ap.add_argument("today", help="YYYY-MM-DD of the briefing you are writing")
ap.add_argument("--prev", type=int, default=3, help="how many previous briefings to scan")
ap.add_argument("--ids", default="", help="comma-separated HN ids considered AI-side")
a = ap.parse_args()


def urlkey(u):
    pr = urlparse(u or "")
    return (pr.netloc.lower() + pr.path).rstrip("/").lower()


files = sorted(f for f in os.listdir(VAULT)
               if re.match(r"\d{4}-\d{2}-\d{2}-AI要闻\.md$", f) and f < a.today + "-AI要闻.md")
files = files[-a.prev:]
prev_ids, prev_urls = {}, {}
for f in files:
    t = open(os.path.join(VAULT, f), encoding="utf-8").read()
    for m in re.finditer(r"item\?id=(\d+)", t):
        prev_ids.setdefault(m.group(1), []).append(f[5:10])
    for m in re.finditer(r"\]\((https?://[^)\s]+)\)", t):
        prev_urls.setdefault(urlkey(m.group(1)), []).append(f[5:10])
print("compared against:", ", ".join(f[5:10] for f in files))

if a.ids:
    ids = [int(x) for x in a.ids.replace(" ", "").split(",") if x]
else:
    ids = [x["id"] for x in json.load(open("/tmp/hn_ai.json"))]
items = {x["id"]: x for x in json.load(open("/tmp/hn_items.json")) if x and x.get("id")}

print("\n=== HN candidates: %d ===" % len(ids))
hits = 0
for i in ids:
    d = items.get(i)
    if not d:
        print("NOT IN TOP250:", i)
        continue
    u = d.get("url") or ("https://news.ycombinator.com/item?id=%d" % i)
    tags = []
    if str(i) in prev_ids:
        tags.append("ID in " + ",".join(sorted(set(prev_ids[str(i)]))))
    if urlkey(u) in prev_urls:
        tags.append("URL in " + ",".join(sorted(set(prev_urls[urlkey(u)]))))
    if tags:
        hits += 1
        print("CROSS | %5s | %s | %s << %s" % (d.get("score"), i, (d.get("title") or "")[:70], " | ".join(tags)))
    else:
        print("NEW   | %5s | %s | %s | %s | c=%s" % (d.get("score"), i, (d.get("title") or "")[:70], u[:80], d.get("descendants")))
print("cross-period hits: %d / %d" % (hits, len(ids)))

print("\n=== AI HOT items whose URL already appeared ===")
n = 0
for it in json.load(open("/tmp/aihot.json"))["items"]:
    k = urlkey(it.get("url"))
    if k in prev_urls:
        n += 1
        print("REPEAT | %s | %s | %s | in %s" % ((it.get("publishedAt") or "")[:16],
              (it.get("title") or "")[:70], (it.get("url") or "")[:70], ",".join(sorted(set(prev_urls[k])))))
print("aihot repeats:", n)
