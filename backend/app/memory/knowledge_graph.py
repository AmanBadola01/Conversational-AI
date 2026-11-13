import logging
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.memory.base import BaseMemory
from backend.app.models.db_models import KGTriple, Message
from backend.app.llm.client import llm_client

logger = logging.getLogger(__name__)

# Trivial conversational words to filter out from the Knowledge Graph
TRIVIAL_WORDS = {"user", "assistant", "bot", "hello", "hi", "question", "answer", "message"}

class KGMemory(BaseMemory):
    """
    4. Knowledge Graph (KG) Memory Technique:
    Extracts Subject-Predicate-Object triples from conversations.
    Stores semantic relationships in PostgreSQL's kg_triples table.
    Queries connected subgraphs relevant to user queries for multi-hop reasoning.
    Powers the interactive force-directed graph visualizer in the React UI.
    """

    # Constructor: Initializes Knowledge Graph Memory for extracting and querying semantic (Subject, Predicate, Object) triples
    def __init__(self):
        super().__init__(memory_type="kg")

    # Relational Retrieval: Queries connected graph triples matching entities in the query and injects relational context
    def get_memory_context(
        self, 
        conversation_id: str, 
        current_query: str, 
        db: Session
    ) -> str:
        # Fetch all relationship triples for this conversation
        all_triples = db.query(KGTriple).filter(
            KGTriple.conversation_id == conversation_id
        ).order_by(KGTriple.created_at.desc()).all()

        if not all_triples:
            return ""

        query_lower = current_query.lower()
        matched_triples = []

        # Find triples where either the Subject or Object is referenced in the user query
        for t in all_triples:
            if t.subject.lower() in query_lower or t.object.lower() in query_lower:
                matched_triples.append(t)

        # Fallback: If no direct keyword match, provide the top 5 most recently created triples
        if not matched_triples:
            matched_triples = all_triples[:5]

        if not matched_triples:
            return ""

        # Format into a clean graph context block for the LLM prompt
        lines = ["[KNOWLEDGE GRAPH RELATIONAL CONTEXT]"]
        for t in matched_triples:
            lines.append(f"- ({t.subject}) --[{t.predicate}]--> ({t.object})")

        return "\n".join(lines)

    # Triple Extraction & Ingestion: Extracts meaningful relationships via Groq, filters trivial noise, and persists triples to PostgreSQL
    async def update_memory(
        self, 
        conversation_id: str, 
        user_message: str, 
        assistant_message: str, 
        source_message_id: str,
        db: Session
    ) -> Dict[str, Any]:
        # Extract relationship triples from the dialogue turn using Groq utility LLM
        extraction = await llm_client.extract_entities_and_triples(
            user_message=user_message,
            assistant_message=assistant_message
        )

        triples_data = extraction.get("triples", [])
        if not triples_data:
            return {"memory_type": "kg", "extracted_triples": 0}

        saved_count = 0
        for item in triples_data:
            sub = str(item.get("subject", "")).strip()
            pred = str(item.get("predicate", "")).strip()
            obj = str(item.get("object", "")).strip()

            # Filter out empty or trivial conversational chatter
            if not sub or not pred or not obj:
                continue
            if sub.lower() in TRIVIAL_WORDS or obj.lower() in TRIVIAL_WORDS:
                continue

            # Check for existing duplicate triple in this conversation to avoid duplicates
            exists = db.query(KGTriple).filter(
                KGTriple.conversation_id == conversation_id,
                KGTriple.subject.ilike(sub),
                KGTriple.predicate.ilike(pred),
                KGTriple.object.ilike(obj)
            ).first()

            # Insert new unique relationship triple into PostgreSQL
            if not exists:
                triple = KGTriple(
                    conversation_id=conversation_id,
                    subject=sub,
                    predicate=pred,
                    object=obj,
                    source_message_id=source_message_id
                )
                db.add(triple)
                saved_count += 1

        db.commit()
        logger.info(f"Knowledge Graph memory saved {saved_count} new triples for conversation {conversation_id}.")
        return {"memory_type": "kg", "extracted_triples": saved_count}

