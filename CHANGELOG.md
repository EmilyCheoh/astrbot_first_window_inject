# Changelog

## v1.1.0

### Added
- 新增持久文本注入模式（persistent_inject）：首轮注入纯文本，不带 XML 标签，后续轮次不会被清理，一直保留在上下文中
- 新增 `tag_inject_enabled` 开关，控制 XML 标签注入模式的启用/禁用
- 新增 `persistent_inject_enabled` 开关，控制持久文本注入模式的启用/禁用
- 新增 `persistent_position` 配置，持久文本的注入位置独立于 XML 标签注入
- 新增 `persistent_content` 配置，持久文本注入的内容
- 两种模式可同时启用、单独使用或全部关闭

### Changed
- 注入逻辑抽取为 `_inject_text` 辅助方法，XML 标签和持久文本共用同一套位置注入逻辑
- 日志输出细化，区分注入的模式和位置

## v1.0.0

### Added
- 初始版本
- 通过 `req.contexts` 条数判定新窗口首轮消息，仅在首轮注入指定内容
- 支持 `initial_context_count` 配置，兼容有/无预设对话的场景
- 三种注入位置：`user_message_before`、`user_message_after`、`system_prompt`
- `user_message_after` 模式下自动检测 LivingMemory 的 `<RAG-Faiss-Memory>` 标签，将内容插入到 RAG 标签之前
- 每轮自动清理上一轮残留的标签内容（覆盖 prompt、system_prompt、contexts 中的字符串、字典、多模态三种消息格式）
- 清理阶段 priority=2，注入阶段 priority=-499，与 PromptTags / LivingMemory 安全共存
- 当两个插件都使用 `user_message_before` 时，PromptTags 的内容在最前面，FirstWindowInject 的内容紧随其后
