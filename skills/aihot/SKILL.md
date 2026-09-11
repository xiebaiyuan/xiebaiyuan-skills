---
name: aihot
description: "Use when 采集 AI 每日要闻/日报。并行拉取 AI HOT + HN API，中文简报入 Obsidian。"
platforms: [linux, macos]
version: 1.0.0
author: xiebaiyuan-hermes
license: MIT
metadata:
  hermes:
    tags: [research, media, news, ai, cron]
    related_skills: [obsidian, trendshift-deep-research, comparison-research]
---

# AI 每日要闻（aihot）

采集今日 AI 社区热点 → 中文简报 → 存 Obsidian + 推送给用户。cron 每日 09:30 运行（job `e4fa4bac2c67`）。

**方法来源**：mattpocock/skills `research` 思路——后台 agent 并行采集、只信一手来源（官方 API，不采信二手转述）、单文件落盘、逐条标注来源。

## 解决什么问题

每天自动把散落在 AI HOT 精选 + HN 热榜的 AI 新闻聚合成一份**带来源标注、可回溯、关联到已有调研库**的中文简报，替代人工刷资讯。

## 数据源（一手来源，直接用官方 API）

### 1. AI HOT（aihot.virxact.com 公开 API）

```bash
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
since=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&since=$since&take=50" -o /tmp/aihot.json
```

分类：`ai-models` / `ai-products` / `industry` / `paper` / `tip`。items 含 `title` / `title_en` / `url` / `source` / `category` / `summary` 字段（summary 是平台精选摘要，直接用）。

### 2. Hacker News（Firebase API）

```bash
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json" -o /tmp/hn_ids.json
# 逐条取详情：https://hacker-news.firebaseio.com/v0/item/{id}.json
```

- 只取 AI 相关（GPT, Claude, LLM, model, agent, OpenAI, Anthropic, deepseek, gemini, mistral, llama, diffusion, vllm, ollama, huggingface, mcp, rag, token 等关键词命中）
- 去重：同故事只保留一个；与 AI HOT 重复的条目合并（标注双源）

## 执行流程

### 1. 并行采集（后台 agent 思路）

AI HOT 与 HN 两路**并行拉取**（`&` + `wait` 聚合），互不等待：

```bash
curl -sH "User-Agent: $UA" "https://aihot.virxact.com/api/public/items?mode=selected&since=$since&take=50" -o /tmp/aihot.json &
curl -s "https://hacker-news.firebaseio.com/v0/topstories.json" -o /tmp/hn_ids.json &
wait
```

> ⚠️ **cron 模式禁止 `curl | python3` 管道和 `python3 -c` 内联**——安全策略会拦截。正确姿势：curl 先 `-o` 落盘，再用 write_file 写处理脚本 → `python3 /tmp/xxx.py` 执行。
>
> 💾 **现成处理脚本**：`scripts/ai_daily_process.py`（**v3.1，2026-09-11 重写**，含 AIHOT 同源去重、HN 合并、实体匹配越界防护、重点精选、分类分组输出；用法：先跑上面两条 curl 落盘 /tmp/aihot.json + /tmp/hn_ids.json，再 `python3 ~/.hermes/skills/research/aihot/scripts/ai_daily_process.py /tmp/ai_brief.md`（**输出路径可用 argv[1] 指定**，默认 /tmp/ai_brief.md），最后 cp 到 vault 目标路径）。脚本会打印一行 `----- backlink debug` 段落，落盘前必须人工修剪误链。

### 2. 数据处理

- AI HOT：提取 items 的 id/title/title_en/url/source/category/summary
- HN：取 top 50 → 逐条拉详情 → 关键词过滤 → 按 score 排序
- 合并去重：标题相似或 URL 相同的条目合并，标注 `— AI HOT + HN（N 分）`
- **同源去重阈值（v3.1 修正，旧规则有严重 bug）**：
  - **禁止**「ratio≥0.30 且共享任意 ≥6 字符 token 即合并」——品牌名（deepseek/anthropic/openai）本身就是 ≥6 字符 token，会把同一公司的不同新闻糊成一条。
  - 正确规则：① **分类不同不合并**（ai-models 公告 vs tip 解读各自成条），除非标题 ratio ≥ 0.75；② 共享「含数字的复合 token」（`v4-1-flash`、`agents-api`，即把 deepseek-v4.1-flash 去品牌后拼成 v4-1-flash）→ 合并；③ 共享 ≥2 个特征 token 且 ratio ≥ 0.35 → 合并；④ 去品牌后标题 ratio ≥ 0.55 → 合并。
  - **合并时 title / url / summary 必须整组取自同一条 item**（取 summary 最长者作代表），其余 URL 进「同源链接：」行。严禁「保留 A 的标题 + 换成 B 的 summary」——2026-09-11 旧脚本就这么干过，产出「Anthropic 蒸馏指控」标题配 DeepSeek V4.1-Flash 摘要的错配条目。
  - HN 与 AIHOT 合并：normalized 标题或 URL 相同，或共享一个「含数字/≥5 字符」的特征 token（HN `DeepSeek v4.1 Flash` 靠 `v4` 与 AIHOT 条目对上，标 `AI HOT + HN（N 分）`）。
- **同源去重的 URL 选择坑**：合并时若想把官方 blog（长 URL）当主链接，需显式 swap 逻辑；实测默认保留先出现者即可，`同源链接：` 行补次要 URL。

### 3. 关联 vault 已有调研（不产生孤岛）

对每条新闻提取实体名，检查 vault 是否有对应调研文档/wiki 实体：

```bash
# 2026-09-01：调研分析/ 顶层已按类别聚类（GitHub项目调研/、网络与配置/、产品对比/、视频调研/ 等），
# 须递归搜索所有子目录，不能只匹配顶层
find ~/AI_DOC/调研分析 -name "*${entity}*调研*.md" 2>/dev/null
find ~/AI_DOC/wiki/entities -name "*${entity}*.md" 2>/dev/null
```

命中则用 `[[wikilink]]` 追加在条目末尾：
- `[[调研分析/{带子目录的相对路径}|📄 调研]]` 或 `[[wiki/entities/{实体名}|📄 wiki]]`
- **优先用 `~/AI_DOC` 快捷路径**（iCloud 慢路径易超时）

**实体匹配实战规则（2026-08-18 修正）**：
- 用 Python `glob.glob` 代替 shell `ls` glob，且必须做 realpath 越界检查——本机曾匹配出 `../hermes_workspace/*` 的越界链接（软链路径解析不一致），`os.path.realpath(p)` 不以 `realpath(~/AI_DOC)` 开头就跳过。
- 英文候选 token 长度 ≥5（`GPT`/`Cut`/`simple` 这类短词会产生 OpenCut、simplex-chat 之类的子串噪音），停用词表加 `simple/fix/best/pricing/model` 等高频噪音词。
- 2026-09-01：调研分析/ 顶层已聚类，调研文档分散在 `GitHub项目调研/`、`产品对比/`、`网络与配置/`、`AI与Agent/`、`视频调研/` 等子目录。用 `find ~/AI_DOC/调研分析 -name "*${entity}*"` 递归搜索（排除 `每日要闻/`、`Trendshift 热门项目/简报/` 等非实体文档所在的简报/日报目录）；wikilink 用带子目录的相对路径。同文件 wiki/entities 与调研分析双份存在时可都保留；每条目最多 2 个链接。
- 匹配不到就跳过，不编造 wiki 链接。

### 4. 输出格式

按 category 分组、全局编号、中文。每组头部：

```markdown
## 🔥 今日重点（3-5 条精选，标注「AI HOT + HN（分数）」双源）
## 📦 产品发布/更新
## 🏭 行业动态
## 📄 论文研究
## 💡 技巧与观点
```

条目模板：
```markdown
1. [标题](url) 🆕 — AI HOT + HN（735 分）
   一句话说明（有 summary 直接用，数字精确）
   > 与 MM-DD 相比：具体变化（有昨日简报时写跟进，无则省略）
   · [[wiki/entities/xxx|📄 wiki]]
```

头部元信息必须包含：日期、覆盖窗口（UTC + 北京）、数据源统计（AI HOT N 条 + HN N 条 AI 相关，去重合并共 N 条）、缺失简报提示（如有）。

### 5. 落盘（单文件）

- 路径：`~/AI_DOC/调研分析/每日要闻/YYYY-MM-DD-AI要闻.md`
- 用 `write_file` 写绝对路径（iCloud 物理路径，Obsidian 自动同步）
- 写后验证：`wc -c` + 首尾抽样 + 无残留 `.h)`/`.html)` 断链

### 6. 信源标注

简报末尾加提示行：哪些条目是 API 原文摘要、哪些是标题概括、哪些细节需以原文为准。数字不约、缩写不猜。

## 已知坑（cron 实战 2026-08-11~18）

1. **cron 模式 `python3 -c` 内联被拦截**：安全策略拒绝内联脚本，报错后无输出。解法：write_file 写 `/tmp/ai_daily_process.py` → `python3 /tmp/ai_daily_process.py`。
2. **并行采集命令的 `&` 被 Hermes terminal 拦截**：`curl ... &` 直接报 "Foreground command uses '&' backgrounding"。解法：顺序执行两条 curl（实测总耗时只差 1-2 秒），或 `background=true` 起一条再跑另一条。
3. **并发实例互相覆盖**：补跑时 09:28 和 09:30 两个 cron 实例同时跑，写同一文件导致内容互相覆盖/合并（21 条 vs 20 条）。解法：补跑前先 `cronjob list` 确认没有正在运行的实例；运行中写文件后 `stat` 观察 mtime 是否还在变化，变了说明有并发实例在写。
4. **iCloud 路径慢**：直接 `ls`/`find` iCloud 路径会超时。优先 `~/AI_DOC` 软链快捷路径。
5. **实体匹配越界/噪音**：shell `ls` glob 曾匹配出 `../hermes_workspace/*` 越界链接，短 token 产生 OpenCut/simplex-chat 类误链。解法见「实体匹配实战规则」（realpath 越界检查 + token ≥5 字母 + 停用词）。
6. **AI HOT 同源重复**：同一新闻常以 X 帖 + 官方 blog 两条收录，需 SequenceMatcher + 共享 token 双层判定合并，否则重点区出现两条同新闻。
7. **`task_push.py` 必须用「有 requests 的 python」执行**（2026-08-21 实测修正）：`hiboards_client.py` 延迟 `import requests`，若 python 无 requests，会静默跳过并在调用 `requests.post()` 时抛 `name 'requests' is not defined`。本机 `/opt/homebrew/bin/python3`（3.14）**无 requests**（此前 08-20 记录说它有 2.33.0 已不成立）；`python3`(Hermes venv) 与 `/usr/bin/python3` 均为 requests 2.31.0 正常。安全做法：直接用 `push-hiboard.sh`（内部用 `python3`）或 `cd ~/skills/today-task && python3 scripts/task_push.py --data /tmp/push_hiboard_task.json`；JSON 由脚本用 stdlib json 构造。先用 `python3 -c "import requests;print(requests.__version__)"` 实测再选解释器，别信旧记录。
8. **实体链接仍有明显误链噪音需人工修剪**：matcher 会把 `Liquid AI`→微软ai教育系列、`fx`→react-native、`AGENTS.md`→XNNPACK、`Activation Energy`→somethingsoff、`CHAP`→Humanoid-GPT/OpenHuman 这类零相关实体误链到条目。落盘前扫一遍 backlink 行，删掉与主题无关的 `[[...]]`（保留如 Apple Silicon 本地推理类真实相关链）。可在处理脚本输出后 `python3 -c` 过滤，或手动 patch。
9. **聚合源 URL 可能与主体错位**：2026-08-20 Anthropic 暂停 RL 训练这条，聚合源（buzzing.cc）把 URL 标成 openai.com 域名，与 Anthropic 主体不符。对头部重点条目核对 URL 域名与标题主体是否一致，不一致在条目下加 ⚠️ URL 核验 标注，别直接采信。
10. **HN 关键词误命中与分数快照（2026-09-11）**：`cognition` 会命中 Douglas Hofstadter 认知科学视频（129 分）、`trust` 会命中 "The Deathray"（含 untrusted，44 分）。脚本已加 `HN_STOP_NON_AI` 拦截表；“正文相关但主题不同” 的条目（如 Kagi Translate）宁可保留并注明“仅按标题与域名归纳”。另注意 **HN 分数是实时值**——同一帖两次抓取会差几分（DeepSeek 935→937），简报里写清是抓取时刻快照，不要当成全天终值。
11. **索引回填是流程的一部分（2026-09-11 补）**：`调研分析/每日要闻/00-索引.md` 有月度表，新简报落盘后必须回填一行（`| MM-DD | [[调研分析/每日要闻/YYYY-MM-DD-AI要闻.md\|date]] | 条数 | 亮点 |`），**插在表头下**（读→合并→写，不重写整表）；条数用 `grep -cE '^[0-9]+\. \['` 数，亮点取前 2-3 条重点标题。此前 09-05～09-10 就没回填，别重蹈覆辙。

## 验证清单

- [ ] `/tmp/aihot.json` 与 `/tmp/hn_ids.json` 均非空（HTTP 200）
- [ ] 简报含头部元信息 + 全局编号 + 分类分组
- [ ] 每条新闻带 URL 与来源标注
- [ ] 文件落盘成功（`wc -c` > 3KB）且 Obsidian 可见
- [ ] 每条的标题与摘要属于同一件事（合并后最容易错配，随机抽 3 条对照原文通读）
- [ ] `00-索引.md` 已回填当日行（条数 = 简报编号条目数）
- [ ] 无残留 `.h)` 断链、无重复编号
