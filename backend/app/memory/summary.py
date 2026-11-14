import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.memory.base import BaseMemory
from backend.app.models.db_models import Message, ConversationSummary, Conversation
from backend.app.llm.client import llm_client
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class SummaryMemory(BaseMemory):
    """
    2. Summary Memory Technique:
    Uses the fast Groq utility LLM to condense older conversation history into a running summary paragraph.
    Triggers condensation every N messages (default: 5).
    Replaces full verbatim dialogue with: Running Summary + Last N Recent Messages.
    Guarantees O(1) amortized token efficiency for long-running discussions.
    """

    # Constructor: Initializes Summary Memory with configurable condensation interval (default: 5 messages)
    def __init__(self, summary_interval: int = settings.DEFAULT_SUMMARY_INTERVAL):
        super().__init__(memory_type="summary")
        self.summary_interval = summary_interval

    # Context Retrieval: Fetches the active condensed summary paragraph from PostgreSQL and formats it for prompt injection
    def get_memory_context(
        self, 
        conversation_id: str, 
        current_query: str, 
        db: Session
    ) -> str:
        summary_record = db.query(ConversationSummary).filter(
            ConversationSummary.conversation_id == conversation_id
        ).first()

        # If a summary exists, inject it into the prompt context block
        if summary_record and summary_record.summary_text:
            return (
                f"[CONVERSATION SUMMARY SO FAR]\n"
                f"{summary_record.summary_text}\n"
                f"(Note: Use this summary for high-level context alongside the recent messages below.)"
            )
        return ""

    # Background Condensation: Summarizes only messages not yet summarized,
    # once at least summary_interval new messages have accumulated.
    async def update_memory(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        source_message_id: str,
        db: Session
    ) -> Dict[str, Any]:
        all_messages = db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).all()

        summary_record = db.query(ConversationSummary).filter(
            ConversationSummary.conversation_id == conversation_id
        ).first()

        # Only the delta since the last summarized message is new work.
        if summary_record and summary_record.last_summarized_message_id:
            ids = [m.id for m in all_messages]
            if summary_record.last_summarized_message_id in ids:
                start = ids.index(summary_record.last_summarized_message_id) + 1
                new_messages = all_messages[start:]
            else:
                new_messages = all_messages
        else:
            new_messages = all_messages

        if len(new_messages) < self.summary_interval:
            return {"memory_type": "summary", "summarized": False}

        current_text = summary_record.summary_text if summary_record else ""

        # Call the utility LLM (Groq) to compress dialogue without consuming Gemini quota
        new_summary = await llm_client.summarize_conversation(
            current_summary=current_text,
            new_messages=new_messages
        )

        last_id = new_messages[-1].id if new_messages else source_message_id
        if not summary_record:
            summary_record = ConversationSummary(
                conversation_id=conversation_id,
                summary_text=new_summary,
                last_summarized_message_id=last_id
            )
            db.add(summary_record)
        else:
            summary_record.summary_text = new_summary
            summary_record.last_summarized_message_id = last_id

        db.commit()
        logger.info(f"Updated ConversationSummary for conversation {conversation_id}")
        return {"memory_type": "summary", "summarized": True, "summary": new_summary}

