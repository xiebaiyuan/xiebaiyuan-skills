---
name: obsidian-docs-link
description: Use when the user wants to 把项目文档关联/同步到 Obsidian Vault（创建 obsidian-docs 软链接），或提到 obsidian-docs、vault docs link。
---

# Obsidian Docs Link

在项目根目录创建软链接指向 Obsidian Vault 文档目录。默认链接名 `obsidian-docs`，避免与项目自带的 `docs/` 或 `doc/` 冲突。

## 执行流程

### 1. 确定 Vault 路径

从 `CLAUDE.md` 读取 Obsidian Vault 路径。找不到或路径模糊 → 询问用户。

**完成标志**: 已拿到确定的 Vault 根路径。

### 2. 确定目标目录

在 Vault 中定位项目的文档目录，优先匹配已有命名风格（如 `项目/<project-name>`）。多个候选项时给出首选和备选。

**完成标志**: 有一个首选目标路径和至少一个备选（或确认只有一个）。

### 3. 检查冲突并确认

```bash
ls -d docs doc 2>/dev/null
```

确认两项后动手，缺一不可：

- Vault 目标目录（用户批准）
- 链接名：默认 `obsidian-docs`；项目已有 `doc/` 或 `docs/` 则强制回避；仅在项目无此目录且用户明确要求时才用 `docs`

**完成标志**: 用户已明确批准目标路径和链接名。

### 4. 创建/更新软链接

```bash
ln -sfn <vault-target-dir> <project-root>/<link-name>
```

若已有同名实体目录/文件会被覆盖 → 先停下询问。

**完成标志**: 软链接已创建。

### 5. 验证

```bash
ls -la <link-name>
```

**完成标志**: 链接解析到用户批准的 Vault 路径。
