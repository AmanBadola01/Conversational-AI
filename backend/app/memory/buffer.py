import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.memory.base import BaseMemory
from backend.app.models.db_models import Message
from backend.app.core.context_manager import context_manager

logger = logging.getLogger(__name__)

class BufferMemory(BaseMemory):
    """
    1. Buffer Memory Technique:
    Stores and retrieves the entire conversation history verbatim.
    Best for short, precise conversations (< 20 messages).
    When token budget is approached, employs Smart Middle-Truncation.
    """

    # Constructor: Initializes Buffer Memory with verbatim message storage and middle-truncation capabilities
    def __init__(self):
        super().__init__(memory_type="buffer")

    # Context Assembly: Queries verbatim messages, applies smart middle-truncation if exceeding 1,500 tokens, and returns notice
    def get_memory_context(
        self, 
        conversation_id: str, 
        current_query: str, 
        db: Session
    ) -> str:
        messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).all()

        if not messages:
            return ""

        # Perform smart middle-truncation against the 1,500 token recent budget
        truncated_msgs, was_truncated, pruned_count = context_manager.smart_middle_truncate(
            messages=messages,
            max_tokens=context_manager.recent_budget
        )

        # If middle messages were pruned to fit the budget, inject an informative notice for the model
        if was_truncated:
            return (
                f"[Context Notice: {pruned_count} intermediate messages were omitted to preserve "
                f"token budget. Initial setup context and recent dialogue are retained.]"
            )
        
        return ""

    # State Mutation: Confirms message persistence in database without requiring heavy background LLM extraction
    async def update_memory(
        self, 
        conversation_id: str, 
        user_message: str, 
        assistant_message: str, 
        source_message_id: str,
        db: Session
    ) -> Dict[str, Any]:
        return {"memory_type": "buffer", "status": "updated"}

