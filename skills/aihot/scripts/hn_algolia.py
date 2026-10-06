# -*- coding: utf-8 -*-
"""Reliable HN story reverse-lookup via Algolia.

WHY THIS EXISTS: `hn_discussions.py lookup <url>` sometimes returns a completely
unrelated story (2026-09-22: qwen-image-2.1 -> Qwen3.6-35B-A3B; the stagehand
repo -> an unrelated Show HN). Algolia search + eyeballing title/url is the
trustworthy path.

Usage: edit QUERIES, run `python3 hn_algolia.py`. For each candidate print
objectID (the HN item id), points, num_comments, title, url. Only adopt an id
whose title AND url clearly match the briefing entry.

  https://hn.algolia.com/api/v1/search?query=<q>&tags=story
      &numericFilters=created_at_i>1758000000&hitsPerPage=6
  tags=story excludes comments; tags=show_hn restricts to Show HN.
  created_at_i>1758000000 is a coarse floor (2025-09-16) — raise it to cut noise.
"""
import json, urllib.request, urllib.parse, time

QUERIES = [
    "MiMo",
]
MIN_TS = 1758000000  # 2025-09-16


def search(q, tags="story"):
    url = ("https://hn.algolia.com/api/v1/search?query=" + urllib.parse.quote(q) +
           "&tags=" + tags + "&numericFilters=created_at_i>%d&hitsPerPage=6" % MIN_TS)
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


for q in QUERIES:
    print("### " + q)
    d = search(q)
    for h in (d.get("hits") or [])[:6]:
        print("   id=%s pts=%-5s c=%-5s %s | %s" % (
            h.get("objectID"), h.get("points"), h.get("num_comments"),
            (h.get("title") or "")[:78], (h.get("url") or "")[:70]))
    if not (d.get("hits") or []):
        print("   --none--", d.get("error", ""))
    time.sleep(0.3)
