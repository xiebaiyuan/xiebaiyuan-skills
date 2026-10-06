#!/usr/bin/env python3
"""Pagine AI HOT mode=all for a window, dedupe by id, dump /tmp/aihot.json.

Usage: edit SINCE (or pass as argv[1], UTC ISO like 2026-09-14T23:35:00Z) then run.
NOTE: the correct paging param is `cursor` (from nextCursor), NOT `page` —
`&page=N` returns the identical payload every time (2026-09-15 finding).
"""
import json, subprocess, sys

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-14T23:35:00Z"
BASE = "https://aihot.virxact.com/api/public/items?mode=all&take=50&since=" + SINCE

items = {}
cursor = None
page = 0
while page < 20:
    page += 1
    url = BASE + (("&cursor=" + cursor) if cursor else "")
    out = "/tmp/_aihot_pg.json"
    subprocess.run(["curl", "-s", "-H", "User-Agent: " + UA, url, "-o", out], check=True)
    d = json.load(open(out))
    batch = d.get("items") or []
    if not batch:
        break
    for it in batch:
        items[it["id"]] = it
    print("page %d: %d items, hasNext=%s" % (page, len(batch), d.get("hasNext")))
    if not d.get("hasNext"):
        break
    cursor = d.get("nextCursor")
    if not cursor:
        break

allitems = list(items.values())
allitems.sort(key=lambda x: x.get("publishedAt") or "", reverse=True)
json.dump({"items": allitems}, open("/tmp/aihot.json", "w"), ensure_ascii=False, indent=1)
print("TOTAL unique:", len(allitems))
print("range:", allitems[-1]["publishedAt"], "->", allitems[0]["publishedAt"])
