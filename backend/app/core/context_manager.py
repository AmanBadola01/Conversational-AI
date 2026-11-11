import logging
import tiktoken
from typing import List, Tuple, Set, Optional, Dict, Any
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize tokenizer (cl100k_base is standard for modern chat models)
try:
    _tokenizer = tiktoken.get_encoding("cl100k_base")
except Exception as e:
    logger.warning(f"Failed to load tiktoken encoding: {e}. Using approximate fallback.")
    _tokenizer = None

def count_tokens(text: str) -> int:
    """Accurately count tokens using tiktoken, falling back to character approximation (~4 chars/token)."""
    if not text:
        return 0
    if _tokenizer:
        try:
            return len(_tokenizer.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 4)


class ContextManager:
    """
    Enforces the strict 4,000-token budget and executes Smart Middle-Truncation.
    Allocations:
      - System Prompt: 500 tokens
      - Memory Context: 1,000 tokens (Summary + Entities + KG)
      - Recent Messages: 1,500 tokens
      - Reserved Generation: 1,000 tokens
    """

    def __init__(
        self,
        total_budget: int = settings.TOTAL_TOKEN_BUDGET,
        system_budget: int = settings.SYSTEM_PROMPT_BUDGET,
        memory_budget: int = settings.MEMORY_BUDGET,
        recent_budget: int = settings.RECENT_MESSAGES_BUDGET,
        generation_budget: int = settings.GENERATION_BUDGET
    ):
        self.total_budget = total_budget
        self.system_budget = system_budget
        self.memory_budget = memory_budget
        self.recent_budget = recent_budget
        self.generation_budget = generation_budget

    def smart_middle_truncate(
        self,
        messages: List[Any],
        max_tokens: Optional[int] = None,
        protected_message_ids: Optional[Set[str]] = None
    ) -> Tuple[List[Any], bool, int]:
        """
        Smart Middle-Truncation Algorithm (Page 6 of Assignment):
        1. Preserves initial setup messages (Head anchor: first 2 messages).
        2. Preserves latest user query and immediate context (Tail anchor: last 3 messages).
        3. Never deletes messages tagged with entity definitions (has_entity_definition = True).
        4. Prunes candidate messages strictly from the middle of dialogue history.

        Returns: (truncated_messages_list, was_truncated, pruned_count)
        """
        budget = max_tokens or self.recent_budget
        protected_ids = protected_message_ids or set()

        if not messages:
            return [], False, 0

        # Calculate current total tokens in message history
        total_tokens = sum(getattr(m, "token_count", count_tokens(getattr(m, "content", ""))) for m in messages)
        if total_tokens <= budget or len(messages) <= 5:
            return messages, False, 0

        # 1. Head Anchor (first 2 messages: setup / prompt requirements)
        head_count = min(2, len(messages))
        head = messages[:head_count]

        # 2. Tail Anchor (last 3 messages: recent context + current query)
        tail_count = min(3, len(messages) - head_count)
        tail = messages[-tail_count:] if tail_count > 0 else []

        # 3. Middle Pool (candidates between head and tail)
        middle = messages[head_count:len(messages) - tail_count] if len(messages) > (head_count + tail_count) else []

        evictable_middle = []
        protected_middle = []
        for m in middle:
            m_id = str(getattr(m, "id", ""))
            has_entity = getattr(m, "has_entity_definition", False)
            if m_id in protected_ids or has_entity:
                protected_middle.append(m)
            else:
                evictable_middle.append(m)

        pruned_count = 0
        # Evict oldest non-protected messages from the middle until within budget
        while evictable_middle and total_tokens > budget:
            removed = evictable_middle.pop(0)
            removed_tokens = getattr(removed, "token_count", count_tokens(getattr(removed, "content", "")))
            total_tokens -= removed_tokens
            pruned_count += 1

        # Recombine preserved middle messages in chronological order
        combined_middle = sorted(
            evictable_middle + protected_middle,
            key=lambda msg: getattr(msg, "created_at", 0)
        )

        result = list(head) + combined_middle + list(tail)
        return result, (pruned_count > 0), pruned_count

    def should_trigger_summarization(self, messages: List[Any]) -> bool:
        """Triggers summarization when buffer approaches 80% of its budget (1,200 tokens)."""
        total_recent_tokens = sum(getattr(m, "token_count", count_tokens(getattr(m, "content", ""))) for m in messages)
        threshold = int(self.recent_budget * 0.80)
        return total_recent_tokens >= threshold

    def calculate_token_breakdown(
        self,
        system_prompt: str,
        memory_context: str,
        messages: List[Any],
        conversation_id: str
    ) -> Dict[str, Any]:
        """Calculates real-time token audit for the UI progress bar."""
        sys_tokens = count_tokens(system_prompt)
        mem_tokens = count_tokens(memory_context)
        recent_tokens = sum(getattr(m, "token_count", count_tokens(getattr(m, "content", ""))) for m in messages)
        total_used = sys_tokens + mem_tokens + recent_tokens

        percent_used = round((total_used / self.total_budget) * 100, 1)
        is_warning = percent_used >= 80.0

        return {
            "conversation_id": conversation_id,
            "total_budget": self.total_budget,
            "system_prompt_tokens": sys_tokens,
            "memory_tokens": mem_tokens,
            "recent_messages_tokens": recent_tokens,
            "generation_reserved_tokens": self.generation_budget,
            "total_used_tokens": total_used,
            "percentage_used": percent_used,
            "is_warning": is_warning
        }

context_manager = ContextManager()
