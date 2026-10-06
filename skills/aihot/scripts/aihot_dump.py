#!/usr/bin/env python3
"""Dump /tmp/aihot.json grouped by category for human curation.

Usage: python3 aihot_dump.py [since-UTC] [outfile]
Writes title / title_en / url / source / first 400 chars of summary per item,
grouped by AI HOT category and sorted newest-first, plus a counts header line.
Read it with read_file in pages (~700 lines each) and curate by hand.
"""
import json, sys

SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-14T23:35:00Z"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/aihot_dump.txt"

d = json.load(open("/tmp/aihot.json"))
items = [i for i in d["items"] if (i.get("publishedAt") or "") >= SINCE]

cats = {}
for it in items:
    cats.setdefault(it.get("category") or "unknown", []).append(it)

order = ["ai-models", "ai-products", "industry", "paper", "tip", "unknown"]
out = ["### CATEGORY COUNTS: " + ", ".join("%s=%d" % (k, len(v)) for k, v in sorted(cats.items(), key=lambda x: -len(x[1])))]
for c in order:
    if c not in cats:
        continue
    lst = sorted(cats[c], key=lambda x: x.get("publishedAt") or "", reverse=True)
    out.append("\n\n########## %s (%d) ##########" % (c, len(lst)))
    for it in lst:
        s = (it.get("summary") or "").replace("\n", " ").strip()
        out.append("\n[%s] src=%s\nT: %s\nTE: %s\nU: %s\nS: %s" % (
            (it.get("publishedAt") or "")[:16], it.get("source") or "-",
            it.get("title") or "-", it.get("title_en") or "-",
            it.get("url") or "-", s[:400]))

open(OUT, "w").write("\n".join(out))
print("wrote %d lines, %d items -> %s" % (len(out), len(items), OUT))
