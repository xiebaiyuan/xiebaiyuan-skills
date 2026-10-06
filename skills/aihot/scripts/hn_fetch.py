#!/usr/bin/env python3
"""Fetch HN top N stories with details, filter AI-related, output /tmp/hn_ai.json.

Usage: curl -s https://hacker-news.firebaseio.com/v0/topstories.json -o /tmp/hn_ids.json
       python3 hn_fetch.py 250
KEEP id + descendants — they are needed for the discussion link
https://news.ycombinator.com/item?id={id} (2026-09-14 user requirement).

KNOWN LIMITATION (2026-09-16): the keyword table only matches the TITLE, so
stories without an AI keyword in the title are silently dropped (Capsule,
dbt Charts, PC-ALM, Strix, mass-surveillance, Apple Watch were all missed at
117-295 points). Never conclude "not on HN" from this filter alone — verify
with hn_discussions.py backfill, which looks up by article URL.
"""
import json, urllib.request, re, sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 250
ids = json.load(open("/tmp/hn_ids.json"))[:N]


def get(i):
    url = "https://hacker-news.firebaseio.com/v0/item/%d.json" % i
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


out = []
for i in ids:
    d = get(i)
    if d:
        out.append(d)
json.dump(out, open("/tmp/hn_items.json", "w"), ensure_ascii=False)

KW = ["gpt", "claude", "llm", "llms", "model", "models", "agent", "agents", "agentic", "openai",
      "anthropic", "deepseek", "gemini", "mistral", "llama", "diffusion", "vllm", "ollama",
      "huggingface", "hugging face", "mcp", "rag", "token", "tokens", "neural", "transformer",
      "inference", "training", "fine-tune", "finetune", "embedding", "vector", "prompt",
      "chatgpt", "copilot", "cursor", "codex", "grok", "qwen", "kimi", "moonshot", "nvidia",
      "cuda", "tpu", "quantization", "quantized", "gguf", "lora", "rlhf", "benchmark",
      "artificial intelligence", "machine learning", "ai ", " ai", "voice model", "image model",
      "video model", "text-to", "speech", "whisper", "sora", "midjourney", "stable diffusion",
      "activation", "context window", "hallucinat", "alignment", "interpretab", "gpu",
      "datacenter", "data center", "robotics", "autonomous", "self-driving", "multimodal"]

STOP = ["cognition", "trust", "ai art", "taipei", "fairy", "train", "braid", "domain", "email",
        "claim", "aims", "chain", "maid", "paid", "wait", "raise", "brain", "analyst"]

ai = []
for d in out:
    title = d.get("title") or ""
    tl = title.lower()
    hit = None
    for k in KW:
        if k in ("ai ", " ai"):
            if re.search(r"\ba\.?i\.?\b", tl):
                hit = "ai"
                break
        elif k in tl:
            hit = k
            break
    if not hit or any(s in tl for s in STOP):
        continue
    score = d.get("score") or 0
    if score < 30:
        continue
    ai.append({"id": d.get("id"), "title": title,
               "url": d.get("url") or "https://news.ycombinator.com/item?id=%d" % d.get("id"),
               "score": score, "descendants": d.get("descendants"),
               "hn": "https://news.ycombinator.com/item?id=%d" % d.get("id"), "kw": hit})
ai.sort(key=lambda x: -x["score"])
json.dump(ai, open("/tmp/hn_ai.json", "w"), ensure_ascii=False, indent=1)
print("scanned %d stories, AI-related %d" % (len(out), len(ai)))
for a in ai:
    print("%4d | c=%-4s | id=%s | %s | %s" % (a["score"], a["descendants"], a["id"], a["title"][:80], a["url"][:70]))
