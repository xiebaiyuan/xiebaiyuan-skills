# skills.sh 每日榜单调研规范（复制即用）

> 2026-08-13 重建：原文件在 2026-08-11 skill 恢复时丢失，本文件从 cron job `de26ad2035c2` 的 prompt 沉淀 + 补 mattpocock research 思路。
> 归属：`trendshift-deep-research` skill 的姊妹数据源规范。cron 排期 01:40 / 13:40（北京），与 Trendshift（01:13/13:13）间隔 ≥1.5h。

## 定位

skills.sh（Vercel 的 Agent Skills 目录站）追踪 **Agent Skill 安装量**热度，与 Trendshift（GitHub Star 热度）互补。skills.sh 头部聚合仓库 GitHub star 往往 <1k（Tier 3），但安装量 20k+——**两个维度独立，不能互相替代**。

**方法出处**：与 mattpocock/skills `research` 三原则对齐：
1. **后台 agent 并行**：榜单抓取 + 每份调研对象可拆给 delegate_task 子 agent 并行（参考 trendshift-deep-research「并行调研模式」章节的 context 模板）
2. **一手来源**：安装量看 skills.sh 页面、元数据走 GitHub API（301 重定向追踪真实 repo）、skill 内容读原始 SKILL.md（不是 README 转述）
3. **单文件落盘 + 逐条引用**：每调研对象一份 `SKILLS/调研/{owner}__{repo}.md`，frontmatter 记来源榜单链接

## 数据抓取

```bash
# 24h Trending
curl -sL "https://r.jina.ai/http://www.skills.sh/trending" -A "Mozilla/5.0"
# Hot（安装量字段形如 `158+158` = 当前值+24h增量）
curl -sL "https://r.jina.ai/http://www.skills.sh/hot" -A "Mozilla/5.0"
# jina 失败 → 直接 curl 原始 HTML 解析
```

页面结构：`[排名 ### skill名 owner/repo 安装量](链接)`，如 `[1 ### find-skills vercel-labs/skills 2.8M](http://www.skills.sh/vercel-labs/skills/find-skills)`。

提取：Top 20 条目的 skill 名、owner/repo、安装量（trending 取 24h 安装量，hot 取增量）、排名变化。

## 🔴 调研环节（核心价值，禁止只抓榜单）

**只抓榜单不调研 = 收集癖（2026-08-05 用户纠正）。** 每个 cron 运行必须：

1. **解析真实 repo**：skills.sh 展示名 ≠ GitHub 真实 repo 名。必须每次实测 301：
   ```bash
   curl -sL -o /dev/null -w "%{url_effective}\n" "https://api.github.com/repos/{展示名}"
   # 返回 /repositories/{id} → 再查 id 拿真实元数据
   curl -s "https://api.github.com/repositories/{id}"
   ```
   🔴 **映射禁止沿用历史结论**（8-04 曾全错位：skills-collective→inference-sh、101-skills→sleekdotdesign、design-layers→runcomfy）。发现与历史不一致，先修历史文档再继续。

2. **筛选**（按真实 repo 去重）：
   - 聚合仓库（一个 repo 打包 N 个 skill）→ 调研仓库本身，列出包含 skills
   - 独立 skill 仓库 → 逐个调研
   - 官方/平台技能（higgsfield、linear、AmazonAppDev、字节 byted-*、prisma）→ 优先
   - 非 GitHub 站点源（open.feishu.cn 等）→ 跳过，标注「非 GitHub repo，站点分发」

3. **每个调研对象必做**：
   - GitHub API 元数据（stars/language/license/created_at/pushed_at/description）
   - **读 SKILL.md**（`https://raw.githubusercontent.com/{owner}/{repo}/main/skills/{skill名}/SKILL.md` 或根目录，main 404 试 master）——skill 的核心资产，不能只看 README

4. **产出调研文档**（`SKILLS/调研/{真实owner}__{真实repo}.md` 或 `...__{skill名}.md`）：
   - 基本信息表（展示名/真实 repo/stars/license/安装量）
   - **`**解决的问题**：` 首行一句话**（2026-08-11 用户要求，禁止名词性分类，必须说清救什么命）
   - 包含 skills / SKILL.md 要点
   - 评价：✅ 亮点/值得装场景、⚠️ 局限/风险、🎯 结论
   - 来源与关联：`来源榜单：[[榜单/YYYY-MM-DD-skills.sh-榜单简报]]`（必写）
   - **每批次新增调研文档 ≤5 份**（超出的标注「待调研」留到下批次）

## 🔴 双向关联（三向闭环，断链 = 白调研）

- **A. 调研文档 → 来源榜单**：frontmatter `source: [[榜单/...]]` + 正文末尾可点击链接
- **B. 简报 → 调研文档**：表格「Vault 关联」列给 `[[SKILLS/调研/xxx|📄 调研]]`（禁止只写「未调研」）+ 简报新增「四、本次新增调研」小节
- **C. index.md → 两者**：「每日榜单」小节登记简报 + 「六、skills.sh 榜单调研」小节登记新调研文档到对应子类

### 闭环验证（写入后必做）

```python
import os
vault = '/Users/xiebaiyuan/AI_DOC'
# 1. 每份新调研文档含来源链接 [[榜单/
# 2. 每份新调研文档含「解决的问题」（grep -c ≥1）
# 3. 简报「本次新增调研」的每个 wikilink 文件存在
# 4. index.md 第六节的每个 wikilink 文件存在
```

## 简报结构（`SKILLS/榜单/YYYY-MM-DD-skills.sh-榜单简报.md`）

- frontmatter：tags [skills.sh, trending, hot, 简报]，created，source
- 一、24h Trending Top 20（表格：排名/skill/作者/安装量/vault关联）
- 二、Hot Top 20（表格：同上，含 24h 增量）
- 三、新上榜/飙升榜（无法对比则跳过）
- 四、本次新增调研 🔴 必写（wikilink 列表 + 一句话要点）
- 五、主题归纳（哪些类型 skill 在涨）
- 六、与 Trendshift 的重合度分析

## 表格 wikilink 写法（🔴 Obsidian 坑）

Markdown 表格里 `[[xxx|别名]]` 的裸 `|` 会被当列分隔符 → 链接断裂。**必须转义为 `[[xxx\\|别名]]`**，链接名内不得有杂散空格。批量替换用行级正则（匹配含 skill 名的整行），不要全局字符串替换；写入后用 Python `ord()` 逐字符验证恰好 1 个反斜杠。

## 失败处理

- 抓取失败（页面结构变化/网络问题）→ 如实说明，**不编造榜单数据**
- API 限流/网络失败导致调研失败 → 标注「⚠️ 调研失败（原因）」
- 涉及凭据一律 [REDACTED]
