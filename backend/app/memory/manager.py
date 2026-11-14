import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.memory.base import BaseMemory
from backend.app.memory.buffer import BufferMemory
from backend.app.memory.summary import SummaryMemory
from backend.app.memory.entity import EntityMemory
from backend.app.memory.knowledge_graph import KGMemory
from backend.app.memory.hybrid import HybridMemory
from backend.app.models.db_models import Conversation, Message
from backend.app.core.config import settings
from backend.app.llm.client import llm_client

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Central Memory Factory & Dispatcher:
    Instantiates and routes memory queries based on conversation settings.
    Dispatches context assembly and post-turn background updates across:
    - BufferMemory
    - SummaryMemory
    - EntityMemory
    - KGMemory
    """

    # Constructor: Initializes the memory factory dictionary with instances of all 4 core memory techniques
    def __init__(self):
        self._instances: Dict[str, BaseMemory] = {
            "buffer": BufferMemory(),
            "summary": SummaryMemory(),
            "entity": EntityMemory(),
            "kg": KGMemory(),
            "hybrid": HybridMemory()
        }

    # Strategy Resolver: Resolves and returns the matching memory class based on conversation.memory_type (defaults to Buffer)
    def get_memory_strategy(self, memory_type: str) -> BaseMemory:
        return self._instances.get(memory_type.lower(), self._instances["buffer"])

    # Unified Context Dispatcher: Dispatches prompt context retrieval to the active memory strategy in one standard call
    def get_context(
        self, 
        conversation: Conversation, 
        current_query: str, 
        db: Session
    ) -> str:
        parts = []

        # Prepend the pre-switch summary if the user previously switched memory types mid-conversation
        if conversation.pre_switch_summary:
            parts.append(
                f"[SUMMARY OF PREVIOUS CONVERSATION]\n"
                f"{conversation.pre_switch_summary}"
            )

        # Fetch the active memory technique's own context (entities, triples, summary, or buffer)
        strategy = self.get_memory_strategy(conversation.memory_type)
        technique_context = strategy.get_memory_context(
            conversation_id=conversation.id,
            current_query=current_query,
            db=db
        )
        if technique_context:
            parts.append(technique_context)

        return "\n\n".join(parts)

    # Unified Mutation Dispatcher: Dispatches post-turn background state updates to the active memory strategy
    async def update(
        self,
        conversation: Conversation,
        user_message: str,
        assistant_message: str,
        source_message_id: str,
        db: Session
    ) -> Dict[str, Any]:
        strategy = self.get_memory_strategy(conversation.memory_type)
        result = await strategy.update_memory(
            conversation_id=conversation.id,
            user_message=user_message,
            assistant_message=assistant_message,
            source_message_id=source_message_id,
            db=db
        )

        # Auto-switch: upgrade long Buffer conversations to Hybrid so facts
        # keep being extracted after the verbatim window gets long.
        config = conversation.memory_config or {}
        if (
            conversation.memory_type.lower() == "buffer"
            and config.get("auto_switch_enabled", True)
        ):
            total = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).count()
            if total >= settings.AUTO_SWITCH_THRESHOLD:
                switched = await self.switch_memory_type(
                    conversation_id=conversation.id,
                    new_memory_type="hybrid",
                    db=db
                )
                db.refresh(conversation)
                result = {**result, "auto_switched": switched}

        return result

    # Memory Type Switcher: Generates a summary of past messages and stores it before switching to the new memory technique
    async def switch_memory_type(
        self, 
        conversation_id: str, 
        new_memory_type: str, 
        db: Session
    ) -> Dict[str, Any]:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return {"status": "error", "message": f"Conversation {conversation_id} not found"}

        old_type = conversation.memory_type
        new_type = new_memory_type.lower()

        # Fetch all past messages to generate a one-time summary of what was discussed so far
        all_messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).all()

        pre_summary = ""
        if all_messages:
            # Generate a single condensed summary of all past messages via Groq utility LLM
            pre_summary = await llm_client.summarize_conversation(
                current_summary=conversation.pre_switch_summary or "",
                new_messages=all_messages
            )

        # Store the summary and update the memory type in one commit
        conversation.pre_switch_summary = pre_summary
        conversation.memory_type = new_type
        db.commit()

        logger.info(f"Switched conversation {conversation_id} from '{old_type}' to '{new_type}' with pre-switch summary.")
        return {
            "conversation_id": conversation_id,
            "previous_memory_type": old_type,
            "new_memory_type": new_type,
            "pre_switch_summary": pre_summary
        }

memory_manager = MemoryManager()
