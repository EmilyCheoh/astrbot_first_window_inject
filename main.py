"""
FirstWindowInject - 新窗口首轮注入插件

仅在每个新对话窗口的第一轮 LLM 请求时，向用户消息中注入指定内容。
支持两种注入模式，可同时启用或单独使用：

1. XML 标签注入（tag_inject）：注入带 XML 标签的内容，第二轮起自动清理
2. 持久文本注入（persistent_inject）：注入纯文本内容，不会被清理，一直保留在上下文中

判定逻辑：
- 当 req.contexts 的条数 <= initial_context_count（可配置）时视为新窗口首轮
- initial_context_count 默认为 0；如果设置了预设对话（如 1 组 user+assistant），
  则应配置为对应的条数（如 2）

与 PromptTags / LivingMemory 兼容：
- 清理阶段 priority=2，在 PromptTags(1) 和 LivingMemory(0) 之前执行
- 注入阶段 priority=-499，在 PromptTags(-500) 之前执行
- 使用独立的标签名称，不会与其他插件的正则交叉匹配

F(A) = A(F)
"""

import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

TAG_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

VALID_POSITIONS = ("user_message_before", "user_message_after", "system_prompt")


def _parse_position(value: str) -> str:
    pos = str(value).strip()
    return pos if pos in VALID_POSITIONS else "user_message_after"


@register(
    "FirstWindowInject",
    "FelisAbyssalis",
    "新窗口首轮注入插件 - 仅在新对话的第一条消息中注入指定内容",
    "1.1.0",
    "https://github.com/EmilyCheoh/astrbot_first_window_inject",
)
class FirstWindowInjectPlugin(Star):

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # 预设对话带来的初始 context 条数
        self._initial_ctx_count = int(config.get("initial_context_count", 0))

        # ---------------------------------------------------------------
        # XML 标签注入模式
        # ---------------------------------------------------------------
        self._tag_enabled = bool(config.get("tag_inject_enabled", True))

        if self._tag_enabled:
            self._tag_position = _parse_position(
                config.get("injection_position", "user_message_after")
            )
            self._tag_name = str(config.get("tag_name", "")).strip()
            raw_content = str(config.get("content", ""))
            self._tag_content = raw_content.replace("\\n", "\n").strip()

            if not self._tag_name or not TAG_NAME_PATTERN.match(self._tag_name):
                logger.warning(
                    "FirstWindowInject: 标签名称为空或包含非法字符，XML 标签注入不生效"
                )
                self._tag_enabled = False
            elif not self._tag_content:
                logger.warning(
                    "FirstWindowInject: 标签内容为空，XML 标签注入不生效"
                )
                self._tag_enabled = False

        if self._tag_enabled:
            self._header = f"<{self._tag_name}>"
            self._footer = f"</{self._tag_name}>"
            self._cleanup_re = re.compile(
                re.escape(self._header) + r".*?" + re.escape(self._footer),
                flags=re.DOTALL,
            )

        # ---------------------------------------------------------------
        # 持久文本注入模式
        # ---------------------------------------------------------------
        self._persistent_enabled = bool(
            config.get("persistent_inject_enabled", False)
        )

        if self._persistent_enabled:
            self._persistent_position = _parse_position(
                config.get("persistent_position", "user_message_after")
            )
            raw_persistent = str(config.get("persistent_content", ""))
            self._persistent_content = raw_persistent.replace("\\n", "\n").strip()

            if not self._persistent_content:
                logger.warning(
                    "FirstWindowInject: 持久文本内容为空，持久注入不生效"
                )
                self._persistent_enabled = False

        # ---------------------------------------------------------------
        # 最终状态
        # ---------------------------------------------------------------
        self._any_enabled = self._tag_enabled or self._persistent_enabled

        if self._any_enabled:
            parts = []
            if self._tag_enabled:
                parts.append(
                    f"XML标签[{self._tag_name}]@{self._tag_position}"
                )
            if self._persistent_enabled:
                parts.append(f"持久文本@{self._persistent_position}")
            logger.info(
                f"FirstWindowInject 初始化完成 "
                f"(模式: {', '.join(parts)}, "
                f"初始context阈值: {self._initial_ctx_count})"
            )
        else:
            logger.warning("FirstWindowInject: 无任何注入模式生效，插件不生效")

    # -------------------------------------------------------------------
    # 格式化
    # -------------------------------------------------------------------

    def _format_tag(self) -> str:
        return f"{self._header}\n{self._tag_content}\n{self._footer}\n"

    # -------------------------------------------------------------------
    # 清理（仅 XML 标签模式需要）
    # -------------------------------------------------------------------

    def _clean_string(self, text: str) -> str:
        cleaned = self._cleanup_re.sub("", text)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def _clean_contexts(self, req: ProviderRequest) -> int:
        """从 contexts 中清除本插件注入的标签，返回清除的片段数。"""
        removed = 0

        # 清理 system_prompt
        if hasattr(req, "system_prompt") and req.system_prompt:
            if (
                isinstance(req.system_prompt, str)
                and self._header in req.system_prompt
                and self._footer in req.system_prompt
            ):
                original = req.system_prompt
                req.system_prompt = self._clean_string(original)
                if req.system_prompt != original:
                    removed += 1

        # 清理 prompt
        if hasattr(req, "prompt") and req.prompt:
            if (
                isinstance(req.prompt, str)
                and self._header in req.prompt
                and self._footer in req.prompt
            ):
                original = req.prompt
                req.prompt = self._clean_string(original)
                if req.prompt != original:
                    removed += 1

        # 清理 contexts
        if hasattr(req, "contexts") and req.contexts:
            filtered = []
            for msg in req.contexts:
                if isinstance(msg, str):
                    if self._header in msg and self._footer in msg:
                        cleaned = self._clean_string(msg)
                        if not cleaned:
                            removed += 1
                            continue
                        if cleaned != msg:
                            removed += 1
                            filtered.append(cleaned)
                            continue
                    filtered.append(msg)

                elif isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        if self._header in content and self._footer in content:
                            cleaned = self._clean_string(content)
                            if not cleaned:
                                removed += 1
                                continue
                            if cleaned != content:
                                removed += 1
                                msg_copy = msg.copy()
                                msg_copy["content"] = cleaned
                                filtered.append(msg_copy)
                                continue
                        filtered.append(msg)

                    elif isinstance(content, list):
                        cleaned_parts = []
                        has_changes = False
                        for part in content:
                            if (
                                isinstance(part, dict)
                                and part.get("type") == "text"
                            ):
                                text = part.get("text", "")
                                if isinstance(text, str):
                                    if (
                                        self._header in text
                                        and self._footer in text
                                    ):
                                        ct = self._clean_string(text)
                                        if not ct:
                                            has_changes = True
                                            continue
                                        if ct != text:
                                            has_changes = True
                                            removed += 1
                                            part_copy = part.copy()
                                            part_copy["text"] = ct
                                            cleaned_parts.append(part_copy)
                                            continue
                            cleaned_parts.append(part)

                        if not cleaned_parts:
                            removed += 1
                            continue
                        if has_changes:
                            msg_copy = msg.copy()
                            msg_copy["content"] = cleaned_parts
                            filtered.append(msg_copy)
                            continue
                        filtered.append(msg)
                else:
                    filtered.append(msg)

            req.contexts = filtered

        return removed

    # -------------------------------------------------------------------
    # 注入辅助
    # -------------------------------------------------------------------

    def _inject_text(self, req: ProviderRequest, text: str, position: str):
        """将文本注入到指定位置。"""
        if position == "user_message_before":
            req.prompt = text + "\n\n" + (req.prompt or "")

        elif position == "system_prompt":
            req.system_prompt = (
                (req.system_prompt or "") + "\n\n" + text
            )

        else:  # user_message_after
            prompt = req.prompt or ""
            rag_marker = "<RAG-Faiss-Memory>"
            rag_pos = prompt.find(rag_marker)
            if rag_pos > 0:
                before_rag = prompt[:rag_pos].rstrip()
                from_rag = prompt[rag_pos:]
                req.prompt = (
                    before_rag + "\n\n" + text + "\n\n" + from_rag
                )
            else:
                req.prompt = prompt + "\n\n" + text

    # -------------------------------------------------------------------
    # 钩子
    # -------------------------------------------------------------------

    @filter.on_llm_request(priority=2)
    async def handle_cleanup(
        self, event: AstrMessageEvent, req: ProviderRequest
    ):
        """清理阶段：仅清理 XML 标签注入的内容。持久文本不受影响。"""
        if not self._tag_enabled:
            return
        try:
            removed = self._clean_contexts(req)
            if removed > 0:
                session_id = event.unified_msg_origin or "unknown"
                logger.info(
                    f"[{session_id}] FirstWindowInject [清理]: "
                    f"已清理 {removed} 处历史注入"
                )
        except Exception as e:
            logger.error(
                f"FirstWindowInject [清理]: {e}", exc_info=True
            )

    @filter.on_llm_request(priority=-499)
    async def handle_inject(
        self, event: AstrMessageEvent, req: ProviderRequest
    ):
        """注入阶段：仅在首轮消息时注入。"""
        if not self._any_enabled:
            return

        try:
            ctx_count = len(req.contexts) if req.contexts else 0

            if ctx_count > self._initial_ctx_count:
                return

            session_id = event.unified_msg_origin or "unknown"
            injected = []

            # XML 标签注入
            if self._tag_enabled:
                self._inject_text(req, self._format_tag(), self._tag_position)
                injected.append(f"XML标签[{self._tag_name}]@{self._tag_position}")

            # 持久文本注入
            if self._persistent_enabled:
                self._inject_text(
                    req, self._persistent_content, self._persistent_position
                )
                injected.append(f"持久文本@{self._persistent_position}")

            logger.info(
                f"[{session_id}] FirstWindowInject [注入]: "
                f"首轮消息，已注入 {', '.join(injected)} "
                f"(当前contexts: {ctx_count}条)"
            )

        except Exception as e:
            logger.error(
                f"FirstWindowInject [注入]: {e}", exc_info=True
            )

    # -------------------------------------------------------------------
    # 生命周期
    # -------------------------------------------------------------------

    async def terminate(self):
        self._any_enabled = False
        self._tag_enabled = False
        self._persistent_enabled = False
        logger.info("FirstWindowInject 插件已停止")
