# xiebaiyuan-skills

个人 AI Agent Skills 仓库。由 [Hermes Agent](https://hermes-agent.nousresearch.com) + [女娲(nuwa-skill)](https://github.com/alchaincyf/nuwa-skill) + [达尔文(darwin-skill)](https://github.com/alchaincyf/darwin-skill) 蒸馏和优化。

Personal AI Agent Skills repository. Distilled by [Hermes Agent](https://hermes-agent.nousresearch.com) + [nuwa-skill](https://github.com/alchaincyf/nuwa-skill) + [darwin-skill](https://github.com/alchaincyf/darwin-skill).

---

## Skills 列表 / Skills List

| Skill | 来源 / Source | 描述 / Description |
|-------|--------------|-------------------|
| [qian-xuesen-cybernetics-thinking](./qian-xuesen-cybernetics-thinking/) | 女娲蒸馏 / nuwa | 钱学森系统控制论思维框架，5 心智模型 + 8 决策启发式 / Qian Xuesen's systems cybernetics thinking framework |
| [engineering-cybernetics-for-work](./engineering-cybernetics-for-work/) | 女娲蒸馏 / nuwa | 工程控制论工作法，反馈闭环+综合集成+层次分解 / Engineering cybernetics methodology for work & learning |
| [performance-optimization-carmack-acton](./performance-optimization-carmack-acton/) | 女娲蒸馏+达尔文优化 / nuwa+darwin | Carmack+Acton 性能优化思维，DOD+SIMD+缓存优化 / Performance optimization mindset from Carmack & Acton |

---

## 安装 / Installation

### 方式 1：npx skills（推荐 / Recommended）

自动安装到所有支持的 agent（Claude Code、Codex、Cursor、Hermes Agent 等 50+ runtime）。

Installs to all supported agents automatically (Claude Code, Codex, Cursor, Hermes Agent, 50+ runtimes).

```bash
npx skills add xiebaiyuan/xiebaiyuan-skills/qian-xuesen-cybernetics-thinking -y -g
npx skills add xiebaiyuan/xiebaiyuan-skills/engineering-cybernetics-for-work -y -g
npx skills add xiebaiyuan/xiebaiyuan-skills/performance-optimization-carmack-acton -y -g
```

### 方式 2：手动安装 / Manual Installation

```bash
# 克隆仓库 / Clone repo
git clone https://github.com/xiebaiyuan/xiebaiyuan-skills.git

# Claude Code
ln -s $(pwd)/xiebaiyuan-skills/* ~/.claude/skills/

# Codex
ln -s $(pwd)/xiebaiyuan-skills/* ~/.codex/skills/

# Hermes Agent
ln -s $(pwd)/xiebaiyuan-skills/qian-xuesen-cybernetics-thinking ~/.hermes/skills/creative/
ln -s $(pwd)/xiebaiyuan-skills/engineering-cybernetics-for-work ~/.hermes/skills/productivity/
ln -s $(pwd)/xiebaiyuan-skills/performance-optimization-carmack-acton ~/.hermes/skills/openclaw-imports/
```

### 方式 3：项目级安装 / Project-level Installation

```bash
# 在你的项目目录下 / In your project directory
mkdir -p .claude/skills/
cp -r path/to/xiebaiyuan-skills/performance-optimization-carmack-acton .claude/skills/
```

### 各 Agent 的 Skills 目录 / Agent Skills Directories

| Agent | 目录 / Directory |
|-------|-----------------|
| Claude Code | `~/.claude/skills/` 或项目 `/.claude/skills/` |
| Codex | `~/.codex/skills/` 或项目 `/.codex/skills/` |
| Cursor | 项目 `/.cursor/skills/` |
| Hermes Agent | `~/.hermes/skills/<category>/` |
| OpenClaw | `skills/` 或项目 `skills/` |

---

## 蒸馏方法论 / Distillation Methodology

使用 [nuwa-skill](https://github.com/alchaincyf/nuwa-skill) 的六路并行采集 + 三重验证方法。

Uses nuwa-skill's 6-agent parallel collection + triple validation methodology.

### 六路采集 / 6-Agent Swarm

1. 著作与系统思考 / Writings & systematic thinking
2. 对话与即兴思考 / Conversations & improvised thinking
3. 表达 DNA / Expression DNA
4. 他者视角与批评 / External views & criticism
5. 决策记录 / Decision records
6. 人物时间线 / Timeline

### 三重验证 / Triple Validation

每个心智模型必须通过：

Each mental model must pass:

1. **跨域复现** / Cross-domain reproduction — 同一框架在 ≥2 个不同领域出现
2. **生成力** / Generative power — 能用此模型推断对新问题的立场
3. **排他性** / Exclusivity — 不是所有聪明人都会这样想

---

## 优化方法论 / Optimization Methodology

使用 [darwin-skill](https://github.com/alchaincyf/darwin-skill) 的 9 维度评估 + hill-climbing 优化。

Uses darwin-skill's 9-dimension rubric + hill-climbing optimization.

### 9 维度评估 / 9-Dimension Rubric

| # | 维度 / Dimension | 权重 / Weight |
|---|-----------------|---------------|
| 1 | Frontmatter 质量 | 7 |
| 2 | 工作流清晰度 / Workflow clarity | 12 |
| 3 | 失败模式编码 / Failure mode encoding | 12 |
| 4 | 检查点设计 / Checkpoint design | 6 |
| 5 | 可执行具体性 / Actionable specificity | 17 |
| 6 | 资源整合度 / Resource integration | 4 |
| 7 | 整体架构 / Overall architecture | 12 |
| 8 | 实测表现 / Tested performance | 23 |
| 9 | 反例与黑名单 / Anti-patterns & blacklist | 6 |

---

## 使用示例 / Usage Examples

### 钱学森系统控制论 / Qian Xuesen's Systems Cybernetics

```
用系统思维分析一下这个架构设计
钱学森视角：应该选择微服务还是单体？
```

### 工程控制论工作法 / Engineering Cybernetics for Work

```
控制论工作法：怎么规划这个项目？
综合集成法：怎么学习一个新的技术栈？
```

### Carmack-Acton 性能优化 / Performance Optimization

```
用 Carmack 的视角分析一下这个热点
DOD 怎么优化这个数据结构？
SIMD 优化：灰度转换要不要写 NEON 版本？
```

---

## 调研素材 / Research Materials

蒸馏过程中的原始调研素材存储在 Obsidian iCloud vault 中：

Raw research materials from distillation are stored in Obsidian iCloud vault:

```
调研分析/钱学森蒸馏素材/          ← 钱学森 6 路采集 (61KB+)
调研分析/Carmack-Acton 蒸馏素材/  ← Carmack+Acton 6 路采集 (61KB+)
```

---

## License

MIT
