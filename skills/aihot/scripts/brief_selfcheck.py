#!/usr/bin/env python3
"""One-shot self-check for a freshly written daily briefing.

Usage: python3 brief_selfcheck.py <path-to-briefing.md>

Checks (all block-level, no external deps except urllib):
  1. every entry whose title line carries an HN marker has BOTH an article
     link and an `item?id=` discussion link in its block  (the skill's
     invariant; both directions have been broken in past briefings)
  2. no item id is used twice inside one entry block
  3. every `item?id=` resolves through the HN Firebase API (catches typos,
     deleted posts, and ids copied from the wrong post)
  4. every [[wikilink]] target exists on disk inside the vault

Exit code 0 when problems == 0. The Firebase pass makes ~1 request per id
(30-40 ids = a few seconds); it is the check that catches wrong links.
"""
import json
import os
import re
import sys
import urllib.request

VAULT = os.path.realpath(os.path.expanduser("~/AI_DOC"))


def main(path):
    txt = open(path, encoding="utf-8").read()
    blocks = re.split(r"(?m)^(?=\d+\. \[)", txt)
    entries = []
    for b in blocks:
        m = re.match(r"^(\d+)\. \[", b)
        if m:
            entries.append((int(m.group(1)), b))

    nums = [n for n, _ in entries]
    print("entries: %d  numbering continuous: %s" % (len(entries), nums == list(range(1, len(nums) + 1))))

    hn_blocks = [(n, b) for n, b in entries if "HN" in b.split("\n")[0]]
    missing = [(n, b.split("\n")[0][:80]) for n, b in hn_blocks
               if "news.ycombinator.com/item?id=" not in b]
    print("entries with HN marker: %d ; missing a discussion link: %d" % (len(hn_blocks), len(missing)))
    for n, head in missing:
        print("   #%d %s" % (n, head))

    dup_in_block = []
    for n, b in entries:
        ids = re.findall(r"item\?id=(\d+)", b)
        if len(ids) != len(set(ids)):
            dup_in_block.append(n)
    print("entries linking the same HN id twice: %s" % (dup_in_block or "none"))

    ids = sorted(set(int(i) for i in re.findall(r"item\?id=(\d+)", txt)))
    bad = []
    for i in ids:
        try:
            with urllib.request.urlopen(
                    "https://hacker-news.firebaseio.com/v0/item/%d.json" % i, timeout=20) as r:
                d = json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001 - report and continue
            bad.append((i, "request failed: %s" % e))
            continue
        if not d or not d.get("title"):
            bad.append((i, "no title (deleted or wrong id)"))
    print("unique HN ids: %d ; unresolvable: %d" % (len(ids), len(bad)))
    for i, why in bad:
        print("   id=%s %s" % (i, why))

    links = re.findall(r"\[\[([^\]\|]+)(?:\|[^\]]*)?\]\]", txt)
    miss = [l for l in sorted(set(links)) if not os.path.exists(os.path.join(VAULT, l))]
    print("wikilinks: %d unique ; missing on disk: %d" % (len(set(links)), len(miss)))
    for l in miss:
        print("   MISSING: %s" % l)

    problems = len(missing) + len(dup_in_block) + len(bad) + len(miss)
    if not nums == list(range(1, len(nums) + 1)):
        problems += 1
    print("PROBLEMS: %d" % problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
