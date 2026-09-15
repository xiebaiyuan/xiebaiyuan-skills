---
name: trendshift-deep-research
description: "Trendshift 每日热门项目深度调研方法论。包含两层评估法（Quick Filter → Deep Dive）、10 维度评估框架、6 章报告结构、GitHub API 量化信号采集、源码分析流程。适用于自动化 cron 调研和手动深度研究。触发词：trendshift、热门项目调研、每日调研、trending、GitHub trending 调研、开源项目分析。"
tags: [research, github, trendshift, evaluation, automation]
---

# Trendshift 深度调研方法论

每日自动调研 Trendshift.io 热门项目的完整工作流。从 Quick Filter 到 6 章深度报告，从量化信号到批判性分析。

**分析框架**：基于工程控制论方法（[[engineering-cybernetics-for-work]]），每个项目的调研遵循「综合集成法」——先定性建地图（Quick Filter），再定量深入（Deep Dive），最终产出可验证的结论。Tier 1 报告的「原理深度解析」章节必须用层次分解法分析架构，用反馈闭环视角分析系统健壮性。

> ⚠️ **2026-08-11 从 cron 输出重建**：本 skill 文件曾丢失（cron 报 `Skill not found and skipped`），已从 `~/.hermes/cron/output/fe9449ce234e/` 的旧运行日志中恢复正文（cron 日志内嵌完整 skill 文本）。恢复时**删除了「调研完成后自动 Star」两段**（用户 2026-08-11 要求：调研只读 stars 元数据，绝不 `gh api -X PUT /user/starred/`）。重建后以下支持文件**不存在**（原始 skill 丢失时一并丢失，cron 日志不内嵌 references/scripts）：`references/cron-prompt-template.md`、`references/sub-agent-deep-research-context.md`、`references/skills-sh-daily-research.md`、`scripts/quality-check.py`。文中对它们的引用按「参考建议」理解即可，不要因文件缺失而中断流程；如重新沉淀这些文件，请放回对应目录。

## 适用场景

- 每日 Trendshift 热门项目自动调研（cron job）
- 手动深度研究某个 GitHub 项目
- 批量评估开源项目的技术价值
- 建立项目知识库和趋势追踪

## 方法出处与 research 对齐

本方法论与 mattpocock/skills `research` skill（2026-08-13 对齐）三原则一致：

| mattpocock research 原则 | 本 skill 落地 |
|:-------------------------|:--------------|
| **后台 agent 并行**（spin up background agent, keep working while it reads） | 「并行调研模式」章节：delegate_task 3 子 agent 并行，Tier 1 分发，父 agent 合并简报 |
| **一手来源**（official docs, source code, specs, first-party APIs — 不采信二手转述） | GitHub API 量化信号 + `git clone` 源码分析（「五、原理深度解析 ⭐」禁止只读 README）；npm 月下载量走官方 registry |
| **单文件落盘 + 逐条引用来源**（single Markdown file, citing each claim's source） | `{owner}__{repo} 技术调研.md` 单文件；信源分级 [实测]/[源]/[推断]/[待验证] + 源链接/下载链接必附 |

差异：mattpocock 的 research 是通用骨架（背景 agent 调研→单文件→存 repo），本 skill 是 GitHub 项目领域的强化版（10 维度评估 + 6 章结构 + 深度门禁 + wiki 三向闭环）。

## 核心方法论：两层评估法

不是所有项目都值得同等深度，但每个项目都应该比 README 摘要深一层。

### Quick Filter（~10秒/项目，所有新仓库必做）

用 GitHub API 获取量化数据，不做主观判断，只采集事实。

**获取 Trendshift 项目列表**（客户端渲染，必须用 browser）：
```javascript
// browser_console 提取（trendshift.io 首页）
(function(){
  const main = document.querySelector('main');
  const links = main.querySelectorAll('a');
  const projects = []; const seen = new Set();
  links.forEach(a => {
    const href = a.getAttribute('href') || '';
    const text = a.textContent.trim();
    if (href.match(/^\/repositories\/\d+$/) && text && !seen.has(text)) {
      const cleanName = text.replace(/^\d+/, '').trim();
      if (cleanName.includes('/')) { seen.add(cleanName); projects.push(cleanName); }
    }
  });
  return JSON.stringify(projects);
})()
```

### 并行批量 API 采集（推荐，批量调研时使用）

同时获取多个 repo 的元数据和 README，比串行快 3-5x：

```bash
# 并行拉取 API 数据（& 后台执行，wait 聚合）
curl -s -o /tmp/repo1.json https://api.github.com/repos/{owner1}/{repo1} &
curl -s -o /tmp/repo2.json https://api.github.com/repos/{owner2}/{repo2} &
curl -s -o /tmp/repo3.json https://api.github.com/repos/{owner3}/{repo3} &
wait && echo "ALL API DONE"

# 并行拉取 README（main 和 master 都试）
curl -sL -o /tmp/readme1.md https://raw.githubusercontent.com/{owner1}/{repo1}/main/README.md &
curl -sL -o /tmp/readme2.md https://raw.githubusercontent.com/{owner2}/{repo2}/main/README.md &
wait && echo "ALL README DONE"

# main 返回 404 的仓库 → 尝试 master 分支
for f in /tmp/readme*.md; do
  if grep -q "404: Not Found" "$f" 2>/dev/null; then
    owner_repo=$(basename "$f" .md | sed 's/readme//')
    curl -sL -o "$f" "https://raw.githubusercontent.com/${owner_repo}/master/README.md"
  fi
done
```

> ⚠️ **不要用 `curl | python3` 管道模式**。安全扫描工具 Tirith 会阻止 pipe-to-interpreter 命令。使用 `-o` 下载到临时文件后单独处理。Piping to `jq` 不受此限制。`&` 后台执行 + `wait` 聚合是安全的。

**🔴 gh api 批量采集的两个坑（2026-08-05 实测踩过）：**

1. **`gh api` 没有 `-o` 参数**（那是 curl 的）。`gh api repos/x/y --jq '...' -o file.json` 会静默失败（`2>/dev/null` 会掩盖错误，循环里表现为「全部 ❌」）。正确写法是 shell 重定向：
   ```bash
   gh api "repos/$r" --jq '{owner: .owner.login, name: .name, stars: .stargazers_count}' > "${owner}__${repo}.json"
   ```
2. **bash 变量名会吞掉 `__` 后缀**：`"$owner__$repo.json"` 被解析为 `${owner__}${repo}.json`（`__` 是合法变量名字符！）→ owner 变量读出来为空，文件名丢前缀，多个同名 repo（如都是 `skills`）互相覆盖只剩最后一个。**必须用花括号 `${owner}__${repo}.json`**。

### 单项目 API 采集

```bash
# 1. 元数据（优先用 gh api，自带 auth 和 retry；curl 作为 fallback）
gh api repos/{owner}/{repo} --jq '{
  stargazers_count, forks_count, open_issues_count,
  subscribers_count, created_at, pushed_at, size,
  language, license: .license.spdx_id, topics
}'
# fallback: curl -s https://api.github.com/repos/{owner}/{repo} -o /tmp/repo.json && jq '{...}' /tmp/repo.json

# 2. 最近 5 个 release（迭代速度）
curl -s https://api.github.com/repos/{owner}/{repo}/releases?per_page=5 -o /tmp/releases.json && jq '.[].tag_name' /tmp/releases.json

# 3. 最近 5 个 open issue（社区活跃度和质量）
curl -s "https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=5&sort=created" -o /tmp/issues.json && jq '.[].title' /tmp/issues.json

# 4. contributor 总数（团队规模）
curl -s "https://api.github.com/repos/{owner}/{repo}/contributors?per_page=1&anon=true" -o /dev/null -w "%{http_code}" -D /tmp/headers.txt && grep -i 'link:' /tmp/headers.txt | grep -oP 'page=\d+' | tail -1
```

**npm 项目额外采集：**
```bash
# 月下载量（真实采用率，比 stars 更有说服力）
curl -s 'https://api.npmjs.org/downloads/point/last-month/{package-name}'

# 版本数（迭代速度）
npm view {package-name} --json | jq '.versions | length'
```

### 分层标准（判定树）

按以下优先级顺序判定，从上到下匹配第一条即停止：

```
收到一个项目（owner/repo）
│
├── 1. 是否已有调研文档？
│   ├── 是 → 归为「信息更新」，不重复分 Tier，调 API 更新 Stars 即可
│   └── 否 → 进入第 2 步
│
├── 2. Stars < 1k？
│   └── 是 → Tier 3（一句话摘要）
│
├── 3. Stars > 5k？
│   ├── 是 → 进入第 4 步（判断是否技术类项目）
│   └── 否 → 进入第 5 步
│
├── 4. 是技术类项目吗？（见下方案例）
│   │   同时满足以下两个条件即可判定为技术类：
│   │   a) 非排除项（not 纯资源合集 / 纯文档站 / 配置文件集）
│   │   b) 满足任一包含项（有代码 / topics 含技术关键词 / 描述含技术关键词）
│   │
│   ├── 是技术类 → Tier 1（6 章深度报告 ≥8KB）
│   └── 不是技术类 → Tier 2（标准调研 ≥5KB）
│
└── 5. Stars 1k ~ 5k？
    │   （注：此区间内即使是非技术类也归 Tier 2，需写调研文件）
    ├── 是 → Tier 2（标准调研 ≥5KB）
    └── 否 → Tier 3（一句话摘要）
```

### 技术类项目判定细则

**排除项（以下类型不算技术类，降级为 Tier 2）：**
- 纯资源合集（awesome-list、curated list、ebook collection、课程链接汇总）
- 纯文档站（文档、教程、教科书，无可运行代码）
- 配置文件集（dotfiles、config 模板）
- 数据集（dataset、images 集合）

**包含项（满足任一即算技术类）：**
- 主要语言是编程语言：Go、Rust、C/C++、Python、TypeScript、Java、Kotlin、Swift、Zig、Ruby
- Topics 包含：`ai` `machine-learning` `deep-learning` `llm` `agent` `database` `monitoring` `devops` `kubernetes` `docker` `infrastructure` `framework` `library` `tool` `cli` `sdk` `platform` `engine`
- 描述中含：`framework` `library` `tool` `engine` `platform` `SDK` `CLI` `server` `runtime` `driver` `agent` `model` 之一

**边界案例参考：**

| 项目 | Stars | 判定 | 理由 |
|:-----|:-----:|:----:|:------|
| HenryNdubuaku/maths-cs-ai-compendium | 5,392 | **Tier 1** | Python + 可运行代码 + AI topics + AI agent MCP |
| 1c7/chinese-independent-developer | 52k | **Tier 2** | 纯资源列表，排除项 |
| jaywcjlove/awesome-mac | 107k | **Tier 2** | 纯资源列表，排除项 |
| microsoft/vscode-docs | 6.5k | **Tier 2** | 纯文档站，排除项 |
| DigitalPlatDev/FreeDomain | 177k | **Tier 2** | 资源列表，排除项 |

**分层不是歧视，是资源分配。** Tier 3 的一句话摘要也要包含 GitHub 地址，方便日后回溯深入。

### 🔴 关键规则：每个 Tier 1/Tier 2 新入库项目必须有 `技术调研.md` 文件

**🔴 索引必需 wikilink（2026-09-01 用户要求）**：索引中每条调研记录必须用 `[[wikilink]]` 指向调研文档，禁止纯文本仓库条目。已调研无文档 → 需补建文档或将链接指到最近似文档；Tier 3 无文档的一律附 GitHub URL 以便跳转复用。

新增项目到索引时，**必须同时生成对应的 `{owner}__{repo} 技术调研.md` 调研文档**。索引中的 wiki link 必须指向存在的文件，禁止纯文本条目（`- librepods-org/librepods — 28,766⭐ | 描述` 不带 `[[ ]]` 是不合格的）。

**检查方法：**
```bash
# 验证索引中每行 Tier 1/Tier 2 项目是否有对应的调研文件
# 正则匹配 `owner__repo 技术调研.md` 存在于文件系统的
# 技术调研文件已细分到 17 个类别子目录，递归统计
find 调研分析 -name '*技术调研.md' | grep -oP '\w+__\w+ 技术调研'
diff <(grep -oP '^\w+/\w+' 索引.md | sort) <(find 调研分析 -name '*技术调研.md' | grep -oP '\w+__\w+' | sort)
```

如果缺少，必须先调研再更新索引，或者调研失败则在索引中标注 `⚠️ 调研失败`。

## 10 维度评估框架（Tier 1 专用）

来自 VC 技术尽调社区的结构化评估体系，每个维度都要有实际数据支撑：

### 1. Popularity（流行度）
- Stars/Forks/Watchers 趋势
- npm 月下载量（如有）
- Star 增长模式（有机增长 vs ProductHunt 暴涨）

### 2. Community（社区健康）
- Contributor 数量和多样性
- Issue 响应速度（创建到回复的时间差）
- Issue 讨论质量（bug report vs feature request？维护者态度？）

### 3. Quality（代码质量）
- 代码目录结构清晰度
- 测试覆盖率（tests 目录？CI 配置？）
- 文档完整性（README、API docs、示例代码）
- Type safety（TypeScript strict? Rust? 有类型定义？）

### 4. Security（安全）
- Semgrep 扫描结果（Tier 1 可 clone 后跑）
  ```bash
  git clone --depth 1 https://github.com/{owner}/{repo}.git /tmp/ts-{repo}
  semgrep --config auto /tmp/ts-{repo} 2>/dev/null | tail -20
  ```
- Dependabot/Renovate 配置
- SECURITY.md 存在与否

### 5. Governance（治理）
- 决策透明度（RFC 流程？CONTRIBUTING.md？）
- License 类型和兼容性
- CLA 要求

### 6. Dependencies（依赖健康）
- 依赖数量和质量
- 已知漏洞依赖
- 依赖更新频率

### 7. Performance（性能）
- Benchmark 数据
- 体积（repo size、打包大小）

### 8. Documentation（文档）
- README 质量（quickstart? API reference? 架构图?）
- 独立文档站
- 示例代码质量

### 9. Momentum（动量）
- 最近 3 个月 commit 频率
- Release 频率
- 最近 push 时间
- 快速迭代 vs 停滞

### 10. Ecosystem（生态位）
- 同类竞品有哪些？
- 与竞品的核心差异？
- 与已有知识库中同类项目的关系？

## 6 章报告结构（Tier 1）

参考标准：Clippings 里的深度调研文章（如 RTK 调研）。每篇 Tier 1 报告必须包含全部 6 章。

### 标准 6 章结构（适用于 AI/工具/基础设施类项目）

### 一、项目概览 + 源链接

结构化信息表：仓库、Star、Fork、版本、语言、License、npm 下载、Contributors、创建时间、最近 Push。

**每个参考模型/工具必须附源链接 + 下载链接：**
- 源链接：HF 仓库 / GitHub 仓库 / 官网（表格中 🔗 列跳转）
- 下载链接：GGUF 直链 / Docker pull / pip install / npm i（表格中 ⬇ 列或独立小节）
- 不得只写名称不写来源

### 二、它是干什么的？
核心价值（一句话）→ 解决的问题 → 解决思路。要有具体的技术描述，不能泛泛而谈。

### 三、部署平台覆盖
评估模型/工具能跑在哪些平台上，每项 ⚠️ 标注兼容性：

| 平台 | LLM 模型 | 传统工具 |
|:-----|:---------|:---------|
| **Server (x86 Linux)** | 默认支持 | ✅ |
| **Desktop (Mac/Win)** | llama.cpp / Ollama | ✅ |
| **Android** | MNN / llama.cpp / MLC LLM | 视情况 |
| **iOS** | MNN / llama.cpp XCFramework | 视情况 |
| **浏览器 (WASM)** | llama.cpp / WebLLM | 视情况 |
| **Edge/嵌入式** | 需极端量化 (1-2bit) | 视情况 |

**对 ML 模型的额外检查：**
- 架构类型：`decoder-only ✅` vs `encoder-decoder ❌（需特殊处理）`
- 推理引擎兼容性：llama.cpp / MNN / MLX / ONNX
- 量化格式：GGUF / AWQ / GPTQ / MLX
- 许可证：Apache-2.0 / MIT / 自定义

### 四、怎么用？
安装命令 → 集成方式 → 核心功能命令表。如果可能，实际运行 `npx {pkg} --help` 验证。

### 五、原理深度解析 ⭐
**报告的核心章节。** 必须从源码中提取，不能只读 README。用工程控制论的层次分解法分析：
- **层次分解**：系统有哪些自然层次？每层的输入/输出/接口是什么？层间怎么协调？
- **反馈闭环**：系统有哪些反馈机制？错误怎么从底层传到上层？有没有容错设计？
- **全局最优分析**：关键设计决策的 trade-off 是什么？牺牲了什么换来了什么？从整体看是全局最优还是局部最优？
- **关键实现**（2-3 个技术细节）
- **技术亮点**（值得学习的设计决策）

**必须 clone 源码：**
```bash
git clone --depth 1 https://github.com/{owner}/{repo}.git /tmp/ts-{repo}
ls /tmp/ts-{repo}/           # 顶层结构
cat /tmp/ts-{repo}/package.json  # 或 Cargo.toml、pyproject.toml
```

### 六、为什么这么火
分析增长原因：时代性问题、名人背书、社区运营、核心优势。
附 10 维度评估摘要表（星级 + 一句话说明）。

### 七、潜在局限 ⭐
**必须有批判性分析：**
- 已知限制和不足
- 适用场景边界
- 与竞品相比的劣势
- 风险点（维护者依赖、技术债、许可证）

### 配置参考式报告结构（适用于配置密集型/基础设施/资源聚合类项目）

对于配置参数丰富、或属于资源聚合（非代码）类的项目（如 awesome-english-ebooks、ComfyUI 自定义节点），可用以下结构替代标准 6 章：

**一、架构概览** — ASCII 数据流图 + 层次分解表。即使项目没有源码架构，也要画出用户操作流程或目录结构。

**二、核心功能配置参考** — 完整参数表（参数名、类型、默认值、说明），从 README/source code 提取，不遗漏任何关键参数。

**三、实用配置场景** — ≥5 个完整示例（Tier 1）/ ≥3 个（Tier 2）。每个示例是从参数表组合出的完整工作流，而非简单的单参数演示。

**四、竞品对比** — 多维度对比表。维度包括：功能覆盖、开源/付费、学习曲线、安装复杂度、资源需求。

**五、适用场景与局限** — 一边写适用场景，一边写已知局限和风险点，批判性分析不可缺少。

**六、运维参考** — 安装方式、调试命令、系统要求、常见问题排查。

> 💡 **何时使用配置参考式**：当项目的主要价值在于丰富的配置选项/参数组合（如代理工具、DNS 工具），或是资源聚合类（如外刊下载），而不是代码实现创新时。标准 6 章和配置参考式都可以产生 ≥8KB 的深度报告，选择取决于项目性质。

## Obsidian Vault 存储流程

> 📁 **2026-09-01 目录统一分类**：`调研分析/` 顶层按 17 个技术类别目录统一收纳所有技术调研文档（AI-Agent与编码Agent/、Skill与插件/、开发者工具/、LLM与模型/ 等），`Trendshift 热门项目/` 类别数据已提升到 `调研分析/` 顶层。（AI-Agent与编码Agent/、Skill与插件/、开发者工具/、LLM与模型/、前端与UI/、基础设施与网络/、音视频与图像/、内容与创意/、数据库与存储/、安全与隐私/、操作系统与桌面/、商业与金融/、社交与通讯/、生活与健康/、生活方式与工具/、游戏与模拟/、硬件与嵌入/）。**新写调研文档默认进 `AI-Agent与编码Agent/` 子目录**（该类占多数）；若项目明显属其他类则写对应子目录。简报/、Tier3摘要、索引仍在顶层。下方示例路径中的 `Trendshift 热门项目/{owner}__{repo}` 应理解为 `Trendshift 热门项目/<类别>/<owner>__{repo}`。



所有调研报告必须存入 Obsidian vault 知识库。

**路径模板：**
```
调研文件：调研分析/AI-Agent与编码Agent/{owner}__{repo} 技术调研.md
简报：     调研分析/Trendshift 热门项目/简报/YYYY-MM-DD-简报.md
```
专题对比文章用描述性文件名，如 `AI编程Agent上下文压缩工具对比 RTK Headroom Lean-ctx 技术调研.md`。

### 主方案：直接写文件到 iCloud 路径（推荐）

直接写文件到 Obsidian vault 的物理路径是最可靠的方式，因为 iCloud 会自动同步，Obsidian 可以读到。

```python
import json, os
from pathlib import Path

vault = "/Users/xiebaiyuan/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI"

def write_research(owner, repo, content):
    """直接写入 Obsidian vault 物理路径（iCloud 自动同步）"""
    path = Path(vault) / "调研分析" / "AI-Agent与编码Agent" / f"{owner}__{repo} 技术调研.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)
```

用 terminal 写 Python 脚本：
```bash
python3 << 'PYEOF'
import json, os
from pathlib import Path
vault = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI")
path = Path(vault) / "调研分析" / "AI-Agent与编码Agent" / "{owner}__{repo} 技术调研.md"
path.parent.mkdir(parents=True, exist_ok=True)
content = """撰写好的 markdown 内容"""
path.write_text(content, encoding="utf-8")
print(f"Written to {path}")
PYEOF
```

> **💡 更简单的选择：`write_file` 工具（主 agent 推荐）**
> 当你在非 cron、非子 agent 的主 session 中时，直接用 `write_file` 工具即可，无需通过 python3 或 obsidian CLI：
> ```
> write_file(path="/Users/xiebaiyuan/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI/调研分析/Trendshift 热门项目/{owner}__{repo} 技术调研.md", content="...")
> ```
> `write_file` 会自动创建父目录、处理含空格的 iCloud 路径，比 python3 terminal 脚本更简洁可靠。**cron 和子 agent 场景仍然用 python3 terminal 方案。**

验证：
```bash
# 确认文件存在且不为空
ls -la "/Users/xiebaiyuan/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI/调研分析/Trendshift 热门项目/{owner}__{repo} 技术调研.md"
# 确认首行正确
head -1 "$_"
```

### 备选方案：子 agent 写文件

当使用 `delegate_task` 让子 agent 批量调研时，子 agent 没有 `execute_code` 工具但可以使用 `terminal`。在 context 中提供完整写入命令模板：

```
# 子 agent context 中写文件的示例命令
python3 -c "
import json
from pathlib import Path
vault = '/Users/xiebaiyuan/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI'
# 从 GitHub API 获取数据
import urllib.request
... 调研逻辑 ...
# 写入调研文件
path = Path(vault) / '调研分析/AI-Agent与编码Agent' / '{owner}__{repo} 技术调研.md'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(content, encoding='utf-8')
print('OK')
"
```

### 更新索引（Trendshift 热门项目索引.md）

索引更新用 `obsidian eval`（因为需要在特定位置插入，不能覆盖写）：

> 💡 **Cron Job 使用者必读**：如果创建或更新 Trendshift cron job，请使用 `references/cron-prompt-template.md` 中的 prompt 模板。该模板将「生成调研文件」作为显式检查项，能有效避免 agent 跳过文件生成步骤。
```bash
obsidian eval 'code=(async()=>{const f=app.vault.getAbstractFileByPath("调研分析/Trendshift 热门项目/Trendshift 热门项目索引.md"); const d=await app.vault.read(f); const marker="### YYYY-MM-DD（第N批）"; const idx=d.indexOf(marker); const insert="### YYYY-MM-DD（第N+1批）\\n\\n**Tier X ...：**\\n- [[文件名]] — 摘要 | Stars | 日期\\n\\n"; const nd=d.slice(0,idx)+insert+d.slice(idx); await app.vault.modify(f,nd); return "done"})()'
```

插入位置：在已有同日批次 header 之前插入新批次。先用 `obsidian eval` 查找所有 `###` header 确定批次编号。

**⚠️ 禁止**：不要用 `read_file` 读 vault 文件后直接 pipe 到 `write_file`——`read_file` 返回 `N|content` 格式会损坏文件。

## 索引维护规则

### 批次分离
同一天多次运行必须用不同段落：
- 今天没有段落 → `### YYYY-MM-DD`
- 已有一段 → `### YYYY-MM-DD（第二批）`
- 已有两段 → `### YYYY-MM-DD（第三批）`
- **绝不合并到已有段落**

### 📐 批次排序规则（重要）
索引整体为倒序（最新日期在最前）。同一天内，新批次插入在旧批次之前：
```
### 2026-07-12（第二批）  ← 新批次在前
### 2026-07-12              ← 旧批次在后
### 2026-07-11（第二批）
### 2026-07-11
```
**验证方法：** `grep "^### " 索引.md | head -10` 确认批次间顺序正确。如果 `（第二批）` 出现在 `### 2026-07-12` 之后，需要交换两者位置。

### 已有项目信息更新 & 🔄 反复上榜追踪（重点，2026-08-30 用户要求）

再次上 trending 的已调研仓库**分两类处理——反复上榜的仓库必须做「近期大更新」深挖，不能只更新 star 数**。

**第一步：识别反复上榜仓库**
- 简便法：读该 repo 调研文档 frontmatter 的 `trending_times:`（上榜累计次数）与 `updated:`（上次调研日期）；
- 全面法：`grep -rl` 近 7-14 天简报（`调研分析/Trendshift 热门项目/简报/`）统计各 owner/repo 出现次数；
- 阈值：近 7 天 ≥2 次 **或** 近 14 天 ≥3 次 → 判为「反复上榜」。

**第二步：普通再次上榜（近 7 天仅 1 次）→ 轻量信息更新**
1. 调 GitHub API 获取最新 Stars/Release/Push
2. 索引原记录追加 `| ↻ YYYY-MM-DD Stars变化`
3. 调研报告更新量化数据 + `updated` 日期

**第三步：反复上榜仓库 → 必有「🔄 近期大更新」小节（重点升级，禁止只更新 star）**
反复上榜说明热度持续，必须挖清「这次为什么又火」的实质变化：
1. **Release/里程碑对比**：`gh api repos/{o}/{r}/releases?per_page=10`，取上次调研（`updated`）之后的新版本；列 tag/时间/release body 亮点；`grep -iE "breaking|deprecat|migrat|大版本"` 抓**主版本跃迁与 breaking changes**。
2. **Commit 活跃度**：`gh api "repos/{o}/{r}/commits?since={updated}T00:00:00Z&per_page=100"` 数 commit 数 + 提炼主题（新 feature/重构/修复）。
3. **Changelog**：抓 CHANGELOG.md / release notes / docs 近更新方向。
4. **Star/Momentum 变化率**：star 增量 ÷ 时间窗口算增速，区分「有机增长」vs「突发暴涨（新 release/大事件/投喂）」。
5. **产出一段「🔄 近期大更新」落地**：
   - 追加到该 repo 调研文档 `## 🔄 近期大更新（YYYY-MM-DD）`：新增版本 / 核心变化 / 为什么反复火 / 更新后的判断；同步 frontmatter `updated:` 与 `trending_times: +1`
   - 索引原记录追加 `| ↻ YYYY-MM-DD +N⭐ 新版本 vX→vY 更新要点`
   - 简报加「🔄 反复上榜追踪」小节：反复上榜仓库一行（仓库 / 近7-14天上榜次数 / 本次star变化 / 最近一次大更新一句话）

### 简报生成（必须步骤）
`YYYY-MM-DD-简报.md` 存放在 `调研分析/Trendshift 热门项目/简报/` 子目录中。包含：
- 项目总数、新调研数、跳过数、遗漏数、信息更新数
- Tier 1 摘要表格（每行加「调研文档」列）
- Tier 2 亮点列表（每行加 `[[wikilink]]` 如果有调研文档）
- Tier 3 一句话摘要（有调研文档加 `[[wikilink]]`）
- 信息更新项目列表（有调研文档加 `[[wikilink]]`）
- 🔄 反复上榜追踪列表（近7-14天上榜≥2/3次的仓库：仓库 / 次数 / star变化 / 最近一次大更新一句话；有调研文档加 `[[wikilink]]`）
- 关键发现（1-3 个）

**调研文档 frontmatter（用于反复上榜自动识别）**：每个新调研文档（Tier 1/2）开头 YAML frontmatter 必须含 `trending_times: 1`、`first_seen: YYYY-MM-DD`、`updated: YYYY-MM-DD`；反复上榜更新时 `trending_times` +1、刷新 `updated`。没有 frontmatter 的旧文档先补上。

### 🚫 禁止自动 Star（2026-08-11 用户要求）

**调研过程中绝对不要给任何 GitHub 项目自动加 Star。**
- 禁止执行 `gh api -X PUT /user/starred/{owner}/{repo}` 或任何修改 star 状态的操作
- 调研只需要**读取** stars 元数据（stargazers_count），不需要改变它
- 如需收藏项目，调研报告中用「值得关注」标记即可，不要操作 GitHub API 写接口

### 关联已有调研文档（简报生成前的关键步骤）

对简报中的**每个项目**（Tier 1/2/3 以及信息更新），检查 vault 中是否存在同名调研文档：
```bash
ls "/Users/xiebaiyuan/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI/调研分析/Trendshift 热门项目/{owner}__{repo} 技术调研.md" 2>/dev/null
```
- 文件存在则添加 `[[调研分析/Trendshift 热门项目/{owner}__{repo} 技术调研|📄 深度调研]]`
- **必须使用 `[[wikilink]]` 格式**，不要用 `obsidian://open?vault=...` URL。WikiLink 在 Obsidian 内可直接跳转、可被 Graph View 追踪、文件重命名自动跟随。同一 vault 内的文件引用永远用 `[[wikilink]]`。

## 并行调研模式（手动执行推荐）

当手动补跑或一次性调研 20+ 个项目时，用 `delegate_task` 并行 3 个子 agent 效率最高（总耗时 ~6 分钟 vs 串行 15+ 分钟）：

**分配策略：**
- Agent 1: 3 个 Tier 1 项目 → `简报-part1.md`
- Agent 2: 3 个 Tier 1 项目 → `简报-part2.md`
- Agent 3: 剩余 Tier 1 + Tier 2 + Tier 3 + 1 个重点 Tier 1 → `简报-part3.md`

**每个子 agent 的 context 必须包含：**
- "Report in Chinese"
- "Clone repos to /tmp/ for source analysis"
- 写入命令模板（`curl -o /tmp/file.json && python3` — 安全扫描器会阻止 `curl | python3` 管道）
- vault 路径
- **深度要求：Tier 1 ≥8KB，Tier 2 ≥5KB，6 章结构**
- **详见 `references/sub-agent-deep-research-context.md`（复制即用的 context 模板）**

**合并流程（父 agent）：**
1. 验证 3 个 part 文件存在：`ls -la 简报/简报-part*.md`
2. 读取每个 part 内容（`terminal cat`）
3. 合并成 `YYYY-MM-DD-简报.md`（含概览+关键发现+详细报告）
4. `obsidian create` + `obsidian append` 写入（chunk <3000）
5. 删除 part 文件
6. 更新索引
7. **运行质量门禁脚本验证深度：** `python3 ~/.hermes/skills/research/trendshift-deep-research/scripts/quality-check.py {owner1}__{repo1} {owner2}__{repo2}`

**子 agent 已知问题：**
- GitHub API curl 可能被限流 → context 中建议用 `gh api repos/{owner}/{repo}` 代替
- `obsidian create` 的 inline content 参数可能被子 agent 安全策略阻止 → fallback 到先 write_file 到 /tmp 再 `cat /tmp/file | obsidian create ...` 或直接 `obsidian create` + `obsidian append`（不带 content 参数，用 stdin）
- 子 agent 可能不理解 obsidian CLI 语法 → context 中给出完整命令示例

## Parallel Execution Pattern

When running manually (not cron), split Tier 1 projects across 2-3 parallel sub-agents to cut total time from ~20min to ~6min. Each sub-agent writes a separate part file.

**Splitting strategy (30 projects):**
- Agent 1: Top Tier 1 projects (headroom, SkillSpector, open-code-review)
- Agent 2: Remaining Tier 1 (open-notebook, Horizon, apple/container)
- Agent 3: Tier 2/3 + one large Tier 1 (superpowers)

**Merge step (required after parallel execution):**
1. Verify all part files exist in Obsidian: `ls 调研分析/Trendshift 热门项目/简报/YYYY-MM-DD-简报-part*.md`
2. Read each part, combine into single `YYYY-MM-DD-简报.md` with overview table at top
3. Write combined file via obsidian create + append (chunk <3000 chars)
4. Delete part files after merge
5. Update index

**Sub-agent context to pass:**
- Vault path: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI/`
- File naming convention: `调研分析/Trendshift 热门项目/{owner}__{repo} 技术调研.md`
- **Include GitHub API URLs for every project** in context so sub-agents don't waste time fetching repo lists:
  ```
  API: https://api.github.com/repos/{owner}/{repo}
  README: https://raw.githubusercontent.com/{owner}/{repo}/main/README.md
  # README fallback: try master branch if main returns 404
  ```
- Preferred write method: `python3` in `terminal` writing directly to vault physical path (NOT obsidian CLI)
  ```python
  from pathlib import Path
  vault = "/Users/xiebaiyuan/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI/"
  path = Path(vault) / "调研分析" / "AI-Agent与编码Agent" / "{owner}__{repo} 技术调研.md"
  path.write_text(content, encoding="utf-8")
  ```
- Explicit instruction: do NOT use `obsidian create` CLI — direct file write to iCloud path
- Note: sub-agents may hit GitHub API 429 — instruct them to fall back to `gh` CLI

## Pitfalls

### 🔴 红灯：绝对不要做

- **不要用模糊的 cron prompt** — 实践表明，如果 cron prompt 只说"调研...并将结果保存到 Obsidian"，即使 skill 里写了"必须生成文件"，agent 也可能跳过文件生成步骤。**Cron prompt 必须把「生成技术调研.md 文件」列为第一优先级的显式产出项**。详见 `references/cron-prompt-template.md`。
- **不要重复 skill 已有内容到 prompt 中** — skill 是单一真相源，prompt 只做任务触发和特殊约束。把 skill 的流程抄到 prompt 里写得越多越容易漏（如漏掉信息更新步骤），还可能与 skill 冲突。正确做法：`执行 Trendshift 每日热门项目深度调研，按 skill 中定义的全流程执行`。
- **不要 pipe 到 python3/ruby/perl** — 安全扫描工具 (Tirith) 会阻止 `curl ... | python3 -c "..."` 等 pipe-to-interpreter 命令。只能用 `-o` 下载到临时文件后单独处理。例如：`curl -s https://api.github.com/repos/owner/repo -o /tmp/repo.json && python3 -c "import json; d=json.load(open('/tmp/repo.json'))"`。Piping to `jq` 不受此限制。
- **不要用 `read_file` 读 vault 文件后直接 pipe 到 `write_file`** — `read_file` 返回 `N|content` 格式会损坏文件。必须用 `obsidian create` + `obsidian append` CLI 命令写入
- **不要编造数据** — 所有量化信号必须来自 API 调用，没有 API 返回就不写
- **不要只读 README** — Tier 1 必须 clone 源码看实现，只看 README 产出的报告质量不达标
- **不要只说好话** — 必须有"潜在局限"章节，缺少批判性分析的报告不合格
- **不要合并索引批次** — 同一天多次运行必须分开段落，绝不合并到已有段落

### ⚠️ 黄灯：需要注意

- **🔴 Obsidian 表格内 wikilink 必须转义管道符（2026-08-05 用户报告「点不出去」）** — Markdown 表格里的 `[[调研/xxx|别名]]` 裸 `|` 会被当成列分隔符、链接断裂；且把短链接塞进宽表格列时，`[[...]]` 内部会残留对齐空格，Obsidian 把空格算进文件名 → 链接失效。**正确写法：`[[调研/xxx\|别名]]`（管道符转义为 `\|`，链接名内不得有杂散空格）**。批量替换表格内容时用行级正则处理（匹配含 skill 名的整行 → 替换「未调研」字段），不要做全局字符串替换；写入后必须用 Python `ord()` 逐字符验证恰好 1 个反斜杠（repr 显示会双重转义，别被 `\\\\` 显示迷惑）。参考 `references/skills-sh-daily-research.md` 的「表格 wikilink 写法」。
- **GitHub repo 改名/迁移导致 wiki link 失效** — 索引中的 `[[owner__repo 技术调研]]` 可能因 repo 从旧所有者迁移到新所有者而成为死链。检测方法：用 GitHub API 查询疑似迁移的 repo，比较 star 数和描述是否匹配。如 `Egonex-AI/Understand-Anything`（72k⭐）实为 `Lum1104/Understand-Anything` 的旧名。发现后更新索引中的 owner 即可。
- **索引批次命名必须查重** — 插入新批次前，先检查已有多少个同日段落（用 `grep -c "### YYYY-MM-DD" 索引.md`），避免产生两个同名"第二批"
- **简报不能跳过** — 这是必须步骤
- **npm 包名不一定是 repo 名** — 如 `@anthropic-ai/claude-code` vs repo `anthropics/claude-code`
- **Semgrep 规则拉取需要时间** — 首次运行 `--config auto` 需要 30-60 秒

### 🔄 Fallback 路径

| 失败场景 | Fallback 方案 |
|---------|--------------|
| GitHub API 429 限流 | 等 60 秒重试；仍失败则用 `gh api repos/{owner}/{repo}` 代替 curl（gh 自带 auth 和 retry）；再失败用 browser 打开 GitHub 页面抓数据 |
| GitHub API 202 异步计算 | 等 10 秒重试（commit_activity 接口首次调用） |
| Trendshift 页面 404 | 直接访问 `trendshift.io/` 首页，用 browser_console 提取项目列表 |
| Trendshift 页面客户端渲染 | 必须用 browser 工具，curl 抓不到内容 |
| `obsidian create` 超时 | 检查 iCloud 同步状态，重试一次；仍失败则用直接写文件到 vault 物理路径（主方案） |
| `obsidian create` + `append` 内容错乱 | 转跳转后的直接写文件方案，不经过 obsidian CLI |
| Clone 超时/网络问题 | 用 GitHub API 的 contents 接口读关键文件，不 clone |
| Cron origin 丢失 | 检查 `~/.hermes/cron/jobs.json` 中 origin 字段，为 None 则手动修复 |
| 手动 `cronjob action='run'` 不生效 | 返回 `success: true` 且设置近未来 `next_run_at`，但 scheduler 不真正执行，`last_run_at` 不更新（2026-06-16 确认为已知限制）。直接在当前 session 手动执行调研流程 |
| Cron run 报 error 但 session 找不到 | 可能在启动阶段就挂了（模型/transport 问题），直接在当前 session 手动跑 |

---

### 🔴 质量标准：深度门禁

每个调研文件必须通过以下质量门禁，不达标的需要重写：

| 检查项 | Tier 1 | Tier 2 | 检测方法 |
|:-------|:------:|:------:|:---------|
| **文件大小** | ≥8KB | ≥5KB | `wc -c` |
| **架构分析** | 必须有数据流图/层次分解 | 建议有 | `grep -c '架构\\|数据流\\|流程'` |
| **配置参考** | 核心参数完整说明 | 关键参数说明 | 目测 |
| **配置场景** | ≥5 个实用示例 | ≥3 个实用示例 | `grep -c '```\\|示例\\|场景'` |
| **竞品对比** | 有对比表 | 有对比表 | `grep -c '对比\\|vs\\|\\|'` |
| **潜在局限** | 必须有 | 建议有 | `grep -c '局限\\|不足\\|缺点\\|注意'` |
| **源链接完整性** | 所有参考模型/工具有 HF/GitHub 链接 | 关键参考有链接 | 目测 |
| **下载链接** | 有直接下载命令/链接 | 建议有 | 目测 |
| **部署平台** | 标注兼容性（server/desktop/mobile） | 建议有 | 目测 |

| 简报分片文件清理 | 3 个子 agent 各生成 part1/part2/part3.md，合并后删除分片 |
| 子 agent obsidian CLI 被阻断 | 主 agent 负责 Obsidian 写入，子 agent 只做调研 |
| heredoc 写 YAML 失败 | 用逐行 `echo >>` 或 `write_file` 工具替代 |
| cron 任务 error 无 session 日志 | 启动阶段就挂了，直接手动跑 |
| Cron status="error" + session 不存在 | `cronjob list` 显示 last_status=error 但 `session_search` 找不到对应 session → job 在 agent 初始化阶段就崩溃了（未进入执行）。诊断：检查 `cron_{job_id}_{timestamp}` 是否存在。修复：直接在当前 session 手动跑完整流程，不要反复重试 cron |
| Skill "not found" 但实际存在 | skill 目录下有 backup 文件（如 `xxx.backup.YYYYMMDD`）导致 `skill_view` 报 "Ambiguous skill name: 2 skills match"，cron 加载也会失败。修复：将 backup 移到 `~/.hermes/skills/_backups/`（专用备份目录，不在 skill 搜索路径中），**然后必须重启 gateway**（`launchctl stop/start ai.hermes.gateway`）清除缓存。纯删文件不够，gateway 缓存了旧的 skill 列表 |
| 依赖任务同时调度导致级联失败 | Wiki Sync 依赖调研完成，必须错开调度。**规则：依赖任务至少间隔 1.5 小时**。**注意：Hermes cron 使用本地时间（北京时间），不是 UTC。** 当前配置：调研 `13 1,13` (北京 01:13/13:13) → Wiki Sync `43 2,14` (北京 02:43/14:43)，间隔 1.5h。也可用 `context_from` 参数让 Wiki Sync 等待调研完成后再运行 |
| 子 agent `obsidian create` 失败 | 子 agent 安全策略可能阻止 inline content。Fallback: 先 write_file 到 /tmp/xxx.md，再 `terminal("cat /tmp/xxx.md | obsidian create path=... content=-")` 或直接写文件到 vault 绝对路径 |

### 🔴 验证步骤：子 agent 完成后必须检查所有文件

子 agent 的完成报告是**自述的，不是经过验证的**。必须独立检查每个预期文件是否存在。2026-07-11 批量补 28 个项目时，子 agent 遗漏了 2 个文件：

```bash
python3 -c "
import os
d = '/Users/xiebaiyuan/Library/Mobile Documents/iCloud~md~obsidian/Documents/AI/调研分析/Trendshift 热门项目'
expected = ['{owner1}__{repo1}', '{owner2}__{repo2}', ...]
for f in expected:
    path = os.path.join(d, f + ' 技术调研.md')
    exists = os.path.exists(path)
    print(f'{\"✅\" if exists else \"❌\"} {f}')
"
```

**已知问题：** 子 agent 经常遗漏极低 star (< 500) 的 Tier 3 项目。这类项目直接在父 agent 手动创建快速调研文件即可。

### 索引更新陷阱：批量 patch 会破坏列表标记

对大型索引文件做多次 `patch` 调用时，可能因上下文不唯一或格式漂移导致 `|- ` 前缀污染。**正确的做法：一次性用 Python 脚本做全部替换，不要逐个 patch**。

```python
with open(path, 'r') as f:
    content = f.read()
replacements = {'旧文本': '新文本（含 [[wikilink]]）', ...}
for old, new in replacements.items():
    if old in content:
        content = content.replace(old, new)
with open(path, 'w') as f:
    f.write(content)
idx = content.replace('||- ', '- ')  # 收尾清理
content = content.replace('|- ', '- ')
```

### 🔴 CHECKPOINT：人工确认点

| 阶段 | CHECKPOINT | 何时暂停 |
|------|-----------|---------|
| Tier 分层完成 | 🔴 CHECKPOINT 1 | 分层结果发给用户确认后再开始深度调研 |
| Tier 1 报告完成 | 🔴 CHECKPOINT 2 | 报告内容发给用户审阅后再写入 Obsidian |
| 简报生成完成 | 🔴 CHECKPOINT 3 | 简报发给用户确认后再更新索引 |

**自动化 cron 场景**：CHECKPOINT 跳过，直接执行全流程。cron 产出的结果自动投递，用户事后审阅。

## Skill 总表（全量台账，2026-09-14 新增）

产物：`调研分析/SKILLS/00-Skill 总表.md`（脚本重写，不要手工改正文；要改就改脚本或 `data/skills_manual.json`）。
它把三处分散的东西合并成一张表：本索引（人工分类）、`SKILLS/榜单/` 简报（上榜日期）、`Skill与插件/` 348 份调研文档（一句话）。

```bash
S=~/.hermes/skills/research/trendshift-deep-research/scripts/skills_ledger.py
python $S update              # 每日：刷新星数（gh api，带缓存）+ 重建总表
python $S update --no-stars   # 不联网，纯本地
python $S check               # 质量门禁：缺中文描述 / 缺分类（退出码 1 = 未通过）
python $S check --since 2026-09-15   # 只查当天新进的条目
python $S report              # 只打印统计
```

- 数据：`~/.hermes/skills/research/trendshift-deep-research/data/` 下 `skills_ledger.json`（台账状态）、
  `skills_stars.json`（星数缓存）、`skills_manual.json`（**人工覆盖层，脚本不覆盖**：`desc`/`cat`/`topic`/`aliases`/`notes`/`deny`）。
- 一句话（干啥的）优先级：调研文档里的 `**解决的问题**：` > index.md 策展要点 > `skills_manual.json` 的 `desc`。
  **所以调研文档里写好「解决的问题」= 总表里自动有描述**，这是最省事的做法。
- 表内含：总览 / 领域分布 / 主台账（342 条，按星数倒序）/ **只上榜未建档待办** / 平台风险样本 / 榜单覆盖。
- **列序硬要求（2026-09-15 用户提出）**：「干啥的」必须在**第 2 列**（紧跟项目名），否则读者要横向滚屏才看得到描述。改脚本时不要把它挪回表尾。


调研产出的蒸馏 Skill 统一管理在 GitHub 仓库：`xiebaiyuan/xiebaiyuan-skills`

**安装方式**：`npx skills add xiebaiyuan/xiebaiyuan-skills/<skill-name> -y -g`
**注意**：PromptScript 不支持全局安装，这是它自己的限制，其他 15+ agent 都正常。
**符号链接**：npx 安装到 `~/.agents/skills/`，Claude Code 自动 symlink，Hermes 需手动 `ln -s ~/.agents/skills/xxx ~/.hermes/skills/<category>/`

## 调研素材管理

蒸馏过程中的原始调研素材存储在 Obsidian iCloud vault：
- 路径：`调研分析/<人物名>蒸馏素材/`
- 包含 6 路采集的 .md 文件 + 原始网页数据
- 不进 Git 仓库（太大），只存 iCloud

## skills.sh 榜单调研（姊妹数据源，2026-08 起每日运行）

skills.sh（Vercel 的 Agent Skills 目录站）是 Trendshift 的姊妹调研流：Trendshift 追踪 GitHub Star 热度，skills.sh 追踪 **Agent Skill 安装量**热度。两个维度独立——skills.sh 头部（101-skills、skills-collective 等聚合仓库）GitHub star 往往 <1k（Tier 3），但安装量 20k+。cron 配置、榜单语义（trending=本周安装量、hot=最近一小时+昨日同时段增量）、简报结构与交叉引用逻辑见 **`references/skills-sh-daily-research.md`**（复制即用）。

### 🔴 只抓榜单不调研 = 收集癖（2026-08-05 用户纠正，必须遵守）

**每日收尾固定动作（2026-09-14 加）：**
1. 写调研文档时，必须带 `**解决的问题**：` 一句话（这行直接进 Skill 总表的「干啥的」列，不写就空白）。
2. 简报写完 + 调研文档写完后，跑 `python ~/.hermes/skills/research/trendshift-deep-research/scripts/skills_ledger.py update`
   把当天内容并入总表，再跑 `check --since <今天>`，退出码必须为 0；
   不通过说明当天新条目缺中文描述或分类——查仓库 README/SKILL.md 后补进 `data/skills_manual.json`（desc/cat/topic）重跑。
3. 总表「只上榜、还没建档」一节是次日待办清单，优先补官方技能 > 独立 skill > 聚合仓库。

用户明确指正：榜单简报里满屏「未调研」标签、不产出调研文档 = **没有沉淀价值**。每个 cron 运行必须：
2. 对「未调研」项目做真实调研（解析真实 repo → API 元数据 → 读 SKILL.md）
3. 产出调研文档到 `调研分析/Skill与插件/{真实owner}__{真实repo}.md`（紧凑结构：基本信息表/是什么/包含 skills/SKILL.md 要点/评价）
4. **🔴 每份调研文档必须说清「它解决了什么问题」（2026-08-11 用户要求）**：「是什么」章节必须以 `**解决的问题**：` 开头写一句话——这个 skill 解决什么痛点、什么场景下的什么失败。禁止只写「XX 类技能/隐蔽调查」这种名词性描述（读者必须不看源码就能答出「这技能是干嘛的、救什么命」）。家族内登顶或上榜的单技能，单独开 `## 深挖：{skill名}` 章节：解决什么问题（一句话）/ 核心方法论（威胁建模、决策表等）/ 关键表格 / 伦理边界 / 为什么火。登顶技能只给表格一行 = 不合格
3. 简报「Vault 关联」列禁止只写「未调研」——要么给调研 wikilink，要么写明跳过原因
4. 每批次新增调研文档 ≤5 份（按优先级：官方技能 > 独立 skill > 聚合仓库，聚合仓库调研一次覆盖全家）

**🔴 三向闭环（用户 2026-08-05 二次纠正：「调研之后要关联回榜单文档和 index 文档，要在任务中明确写清楚」）——调研完必须把关联写回，断链 = 白调研：**
- **A. 调研文档 → 来源榜单**：frontmatter 写 `source: "[[榜单/YYYY-MM-DD-...]]"` + 正文末尾「来源与关联」小节
- **B. 简报 → 调研文档**：表格关联列给 `[[调研分析/Skill与插件/xxx|📄 调研]]`，且简报新增「本次新增调研」小节列全部新文档链接
- **C. index.md → 两者**：「每日榜单」小节登记简报 + 「六、skills.sh 榜单调研」小节登记新调研文档到对应子类
- **写入后必须做闭环验证**（三方向链接全部可达：调研文档含来源链接、简报链接文件存在、index 链接文件存在）

完整调研环节规范（筛选规则、必做动作、文档结构、成本控制、闭环验证脚本）见 **`references/skills-sh-daily-research.md` 的「调研环节」和「双向关联」章节**。

### ⚠️ skills.sh 仓库名 ≠ GitHub 真实 repo 名（2026-08-05 实测修正版）

skills.sh 上的 owner/repo 是**聚合展示名**，API 会 301 重定向到完全不同的 GitHub 仓库。**8-04 批次曾把映射全部写错位**（skills-collective→inference-sh、101-skills→sleekdotdesign、design-layers→runcomfy），8-05 实测 API 301 纠正为：

| skills.sh 名称 | 真实 GitHub repo（实测） |
|---------------|--------------------------|
| skills-collective/skills | **runcomfy-com/skills**（⭐12） |
| 101-skills/skills | **inference-sh/skills**（⭐680） |
| design-layers/agent-skills | **sleekdotdesign/agent-skills**（⭐489，vault 已调研） |

**🔴 规则：映射必须每次 cron 运行重新实测 301，禁止沿用历史结论。** 发现与历史不一致时，先修正历史文档（调研文档的「skills.sh 展示名」字段、Tier3 摘要、旧简报）再继续，否则调研文档/简报链接会挂到错误 repo。

```bash
# 追踪重定向拿真实 repo（返回 /repositories/{id} 形式）
curl -sL -o /dev/null -w "%{url_effective}\n" "https://api.github.com/repos/{skills.sh名字}"

# 用返回的 repository id 查询真实元数据
curl -s "https://api.github.com/repositories/{id}" -o /tmp/qf.json
```
重定向后若真实 repo 与 vault 已调研的相同（如 sleekdotdesign/agent-skills），按「信息更新」处理而非新建调研。

## 相关 Skill

- **technical-research** — 基础调研方法和报告格式
- **hv-analysis** — 横纵分析法（更深度的单项目研究，产出 1-3 万字 PDF）
- **llm-wiki** — 知识库积累和交叉引用
- **obsidian** — Vault 操作
- **engineering-cybernetics-for-work** — 工程控制论方法（Tier 1 报告用层次分解+反馈闭环分析架构）
- **qian-xuesen-cybernetics-thinking** — 系统控制论思维（全局最优分析）
