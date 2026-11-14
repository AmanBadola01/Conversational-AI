import logging
from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.app.memory.base import BaseMemory
from backend.app.memory.summary import SummaryMemory
from backend.app.memory.entity import EntityMemory
from backend.app.memory.knowledge_graph import KGMemory

logger = logging.getLogger(__name__)


class HybridMemory(BaseMemory):
    """
    5. Hybrid Memory Technique:
    Combines Summary (macro) + Entity (micro) + Knowledge Graph (relational)
    context in one prompt block, and runs all three background updaters
    after each turn. Best for long-running mixed conversations.
    """

    def __init__(self):
        super().__init__(memory_type="hybrid")
        self._summary = SummaryMemory()
        self._entity = EntityMemory()
        self._kg = KGMemory()

    def get_memory_context(
        self,
        conversation_id: str,
        current_query: str,
        db: Session
    ) -> str:
        parts = []
        for strategy in (self._summary, self._entity, self._kg):
            context = strategy.get_memory_context(
                conversation_id=conversation_id,
                current_query=current_query,
                db=db
            )
            if context:
                parts.append(context)
        return "\n\n".join(parts)

    async def update_memory(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        source_message_id: str,
        db: Session
    ) -> Dict[str, Any]:
        results: Dict[str, Any] = {"memory_type": "hybrid"}
        for name, strategy in (
            ("summary", self._summary),
            ("entity", self._entity),
            ("kg", self._kg),
        ):
            try:
                results[name] = await strategy.update_memory(
                    conversation_id=conversation_id,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    source_message_id=source_message_id,
                    db=db
                )
            except Exception as e:
                logger.error(f"Hybrid {name} update failed: {e}")
                db.rollback()
                results[name] = {"error": str(e)}
        return results
