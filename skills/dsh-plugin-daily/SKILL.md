---
name: dsh-plugin-daily
description: Use when 每日监控调研 DeepSeek Harness (dsh) 插件生态，轮询多信源归类优质插件并出简报。
---

# dsh 插件每日调研

**解决的问题**：DeepSeek Harness 插件生态每天新增大量项目（topic:dsh-plugin 2026-08 从 882 暴涨到 8742），人工盯不过来。每日自动轮询多信源 → 归类统计优质插件 → 产出中文简报入 Obsidian → 交叉关联其它调研任务。

> ⚠️ 名称澄清：`dsh.fish` 不是 fish shell 工具，而是 **DeepSeek Harness 的插件注册中心**（website dsh.fish + hub 插件 + CLI `@dsh-fish/cli`），官方钦定的生态索引，带 S/A/B/C 质量评分与 API。是**一级信源**（见下）。别和你本机用的 fish shell 混淆。

## 触发
每日 cron 在凌晨 01:00 左右自动执行。也可手动 `cronjob run dsh-插件每日雷达`。

## 信源清单（每日轮询，按优先级）

### 一手 / 数据源
1. **GitHub topic API**（主数据源，最权威）：
   - 总数：`curl -s "https://api.github.com/search/repositories?q=topic:dsh-plugin&per_page=1"` → `total_count`
   - 按星数 TOP：`...&sort=stars&order=desc&per_page=20`
   - 新增（按创建时间）：`...&sort=created&order=desc&per_page=20`
   - 活跃（按推送）：`...&sort=updated&order=desc&per_page=20`
   - 查具体仓库星数：`https://api.github.com/repos/<owner>/<repo>`
2. **GitHub 话题页**：https://github.com/topics/dsh-plugin （看最新上热门）

### 官方注册中心（一级信源，重点）★★★★
3. **dsh.fish**（`stvlynn/dsh.fish`）——DeepSeek Harness 插件注册中心：网站 https://dsh.fish、CLI `npx @dsh-fish/cli add <id>`、hub 插件（`dsh plugin --profile web add github:stvlynn/dsh.fish#main` 注册 hub_search/hub_install 等 7 工具）。带**公开可复现的质量评分 S/A/B/C**（权重 popularity 0.4 / maintenance 0.3 / quality 0.3）+ 7d/30d 星速 + commit 溯源 + 六语言。**评分公式 API**：`https://dsh.fish/api/v1/scoring`；每小时重爬。用它交叉验证 topic API 的"优质"判断。
   - 插件类型：按实际可加载分类 bundle/profile/skill/MCP server/agent preset/hook bridge（探测 package.json / SKILL.md / agent.cordis.yml），非自声明标签。

### 策展目录（人工筛选，质量参考）
4. **dsh-plugins.net/zh/** — 人工策展目录，收录 ~810 项目，标注"来源可追溯"。解析：抓 HTML，正则从 JSON-LD 抽插件条目：
   `re.findall(r'\{"@type":"SoftwareSourceCode","@id":"[^"]*?/plugins/([^"/]+)/#project","url":"[^"]*?/plugins/\1/","name":"([^"]+)"\}', html)` → (slug, name) 列表，与昨日 diff 找新增。
5. **dshplugin.dev/** — 另一目录站（探测 200，无 /zh/ 后缀）。
6. **dshplugins.com/** — 另一目录站（探测 200）。

### 其它精选列表（辅助）
7. **awesome-dsh-plugin/awesome-dsh-plugin**（精选列表，10150★）
8. **0xsline/awesome-deepseek-harness**（生态目录）
9. **AdamPlatin123/awesome-dsh-plugins**（雷达：先收录候选，测试合格进精选）

### 第三方插件市场（8 月中下旬新增，重点盯）
10. **bradeGithub/DSH-Plugins-Marketplace**（126★ → 动态）
11. **dshplugin/dsh-plugin-hub**（社区内置插件市场）
12. **V1ki/dsh-plugin-subscriptions**（171★，Codex/Claude/Grok 订阅接入）

### 关联任务交叉
- Trendshift 深度调研（`trendshift-deep-research` skill）：dsh 生态项目常上热门榜，互相参照
- skills.sh 每日榜单（同 skill）：看哪些 dsh 相关 skill 上榜
- AI 每日要闻（`aihot`）：dsh/DeepSeek 大新闻
- 本资料夹 05-插件生态介绍 / 16-生态汇入全景（历史基线）

## 工作流

1. **快照基线**：读取本资料夹 00-索引.md 里的上次统计（总数/日期），与今日对比。
2. **轮询信源**：并行拉 topic API（总数/星数/新增/活跃）+ dsh.fish（评分/rising）+ 两个策展目录 + 3 个市场。
3. **归类统计**：按类别（TUI/桌面、视觉、记忆进化、预设路由、多Agent、搜索内容、沙箱安全、皮肤娱乐、索引工具链、市场基建、提供商接入、Web UI）整理新增与爬升的优质插件。判断"优质"：星数增速 + dsh.fish 评分 + 近期有 commit + 能被 `dsh plugin add`（npm bundle）。
4. **识别新趋势**：新冒出的市场/赛道/爆款（如 mirage 统一虚拟文件系统、dsh.fish 注册中心、商务商业化整族、订阅市场）。
5. **写每日简报**：存入 Obsidian `调研分析/DeepSeek Harness/dsh插件每日雷达/YYYY-MM-DD.md`，2-4KB 简报，含：今日生态快照表 / 新增优质插件表 / 星数爬升榜 / 新市场新赛道 / 风险提示。更新该目录 00-索引.md（追加不覆盖，diff 校验）。中文人话、具体数字、表格、信源链接、标注 [源]/[推断]。
6. **交叉关联**：在简报里链接相关 Trendshift 热门项目 / skills.sh 上榜项 / AI 要闻热点。
7. **推送**：
   - Telegram：总结当天要点（中文，含关键数字与 2-3 个重点插件）。
   - 负一屏：`python ~/skills/today-task/scripts/task_push.py --name "dsh插件雷达 <MM-DD>" --content "<markdown 摘要>" --result "已完成"`（内容简洁，负一屏不适合长文）。

## 输出质量规则
- 中文、无 emoji 标题、避免加粗列表刷屏、短句、具体数字（星数/仓库数/日期精确）。
- 信源要有直接链接；数字标注 [源: api/<repo>] 或 [推断]。
- 星数是快照值，注明抓取日期。

## 陷阱
- topic:dsh-plugin 混入泛 AI 项目（如 colleague-skill、OpenPencil）——按与 dsh 关联度筛选，认准能 `dsh plugin add` 的 npm bundle 才是真插件 [推断]。
- GitHub API 未认证限速 60 次/时——批量查询合并成一次 search 调用，别逐仓库请求。
- 目录站 810 条目里大量 0-2★ 试水作——优质筛选看增速 + dsh.fish 评分 + commit 活跃度，别只看绝对星数。
- 拼写：`dsh plugin --profile web add` 是真正装法源码；README 可能比代码长（雏形警示）[推断]。
- iCloud vault 0 字节文件 = 未同步，写完 `ls` 确认落地。

## 验证
- 写完后 `wc -c` 确认文件非空且 > 0 字节。
- `cat 00-索引.md` 确认更新时间戳与新增行已追加。
- `cronjob list` 确认任务 last_status: ok。
