# FirstWindowInject - 新窗口首轮注入插件

一个轻量级 AstrBot 插件，仅在每个新对话窗口的第一轮 LLM 请求时向用户消息中注入指定内容。第二轮起自动清理残留，不再注入。

## 功能特性

- 通过 `req.contexts` 条数判定是否为新窗口首轮消息
- 支持有预设对话和无预设对话两种场景（通过 `initial_context_count` 配置）
- 三种注入位置可选：
  - `user_message_before` — 注入到用户消息**前面**
  - `user_message_after` — 注入到用户消息**后面**
  - `system_prompt` — 追加到系统提示词末尾
- 第二轮起自动从对话历史中清理上一轮注入的标签内容
- 与 PromptTags、LivingMemory 插件安全共存，互不干扰

## 判定逻辑

| 场景 | `initial_context_count` | 首轮时 contexts 条数 | 是否注入 |
|------|------------------------|---------------------|---------|
| 无预设对话 | 0 | 0 | 注入 |
| 有一组预设对话（user+assistant） | 2 | 2 | 注入 |
| 第二轮及之后 | — | > 设定值 | 不注入 |

## 与其他插件的共存

- **清理阶段** `priority=2`：在 PromptTags(1) 和 LivingMemory(0) 之前执行
- **注入阶段** `priority=-499`：在 PromptTags(-500) 之前执行，确保两者都用 `user_message_before` 时 PromptTags 内容在最前面
- 使用独立的标签名称，各插件正则不会交叉匹配

## 安装

将 `first_window_inject` 文件夹放入 AstrBot 的插件目录，重启 AstrBot 即可。

## 配置

在 AstrBot 的 Web 后台中配置：

| 字段 | 说明 |
|------|------|
| **初始 context 条数** | 新窗口首轮时 contexts 中已有的条数。无预设对话填 `0`，有一组预设对话填 `2` |
| **注入位置** | 内容注入的位置（用户消息前 / 用户消息后 / 系统提示词） |
| **标签名称** | XML 标签名，如 `First-Window-Context`（不含尖括号，仅限字母、数字、连字符、下划线） |
| **注入内容** | 首轮消息时注入的文本 |

## 开发信息

- **作者**: Felis Abyssalis
- **版本**: 1.0.0
- **依赖**: 无额外依赖，仅使用 AstrBot 内置 API
