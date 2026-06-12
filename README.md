# xiebaiyuan-skills

个人 AI Agent Skills 仓库。由 [Hermes Agent](https://hermes-agent.nousresearch.com) + [女娲(nuwa-skill)](https://github.com/alchaincyf/nuwa-skill) + [达尔文(darwin-skill)](https://github.com/alchaincyf/darwin-skill) 蒸馏和优化。

## Skills 列表

| Skill | 来源 | 描述 |
|-------|------|------|
| [qian-xuesen-cybernetics-thinking](./qian-xuesen-cybernetics-thinking/) | 女娲蒸馏 | 钱学森系统控制论思维框架，5 心智模型 + 8 决策启发式 |
| [engineering-cybernetics-for-work](./engineering-cybernetics-for-work/) | 女娲蒸馏 | 工程控制论工作法，反馈闭环+综合集成+层次分解 |
| [performance-optimization-carmack-acton](./performance-optimization-carmack-acton/) | 女娲蒸馏 + 达尔文优化 | Carmack+Acton 性能优化思维，DOD+SIMD+缓存优化 |

## 蒸馏方法论

使用 [nuwa-skill](https://github.com/alchaincyf/nuwa-skill) 的六路并行采集 + 三重验证方法：

1. 著作与系统思考
2. 对话与即兴思考
3. 表达 DNA
4. 他者视角与批评
5. 决策记录
6. 人物时间线

每个心智模型通过三重验证：跨域复现 + 生成力 + 排他性。

## 优化方法论

使用 [darwin-skill](https://github.com/alchaincyf/darwin-skill) 的 9 维度评估 + hill-climbing 优化：

- 结构维度（59分）：Frontmatter、工作流清晰度、失败模式编码、检查点设计、可执行具体性、资源整合度
- 效果维度（35分）：整体架构、实测表现
- Meta-skill 维度（6分）：反例与黑名单

## 安装

```bash
# 克隆到本地
git clone https://github.com/xiebaiyuan/xiebaiyuan-skills.git

# 链接到 Hermes skills 目录
ln -s ~/xiebaiyuan-skills/qian-xuesen-cybernetics-thinking ~/.hermes/skills/creative/
ln -s ~/xiebaiyuan-skills/engineering-cybernetics-for-work ~/.hermes/skills/productivity/
ln -s ~/xiebaiyuan-skills/performance-optimization-carmack-acton ~/.hermes/skills/openclaw-imports/
```

## License

MIT
