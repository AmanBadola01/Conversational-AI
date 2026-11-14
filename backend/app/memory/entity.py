import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.memory.base import BaseMemory
from backend.app.models.db_models import Conversation, Entity, EntityHistory, Message
from backend.app.llm.client import llm_client

logger = logging.getLogger(__name__)

class EntityMemory(BaseMemory):
    """
    3. Entity Memory Technique:
    Tracks entities (people, organizations, projects, technologies, dates, etc.).
    Maintains a dynamic entity fact store in PostgreSQL.
    Records fact evolution version history (v1 -> v2) in entity_history.
    Injects matching entity facts into the LLM prompt.
    Supports cross-session memory via global entities (is_global=True).
    """

    # Constructor: Initializes Entity Memory for structured fact tracking and versioned attribute evolution
    def __init__(self):
        super().__init__(memory_type="entity")

    # Context Retrieval: Matches entities mentioned in the query and injects their verified facts into the prompt
    def get_memory_context(
        self, 
        conversation_id: str, 
        current_query: str, 
        db: Session
    ) -> str:
        # Retrieve this conversation's entities plus the owner's globals only,
        # so one account's profile facts never enter another account's prompt.
        owner = db.query(Conversation.user_id).filter(Conversation.id == conversation_id).first()
        owner_id = owner[0] if owner else None
        all_entities = db.query(Entity).filter(
            (Entity.conversation_id == conversation_id)
            | ((Entity.is_global == True) & (Entity.user_id == owner_id))
        ).all()

        if not all_entities:
            return ""

        query_lower = current_query.lower()
        matched_entities = []

        # Tier 1: Fast direct name matching in query (0 ms, 0 tokens)
        for ent in all_entities:
            if ent.name.lower() in query_lower:
                matched_entities.append(ent)

        # Tier 2: If no direct keyword match, fallback to the 3 most recently updated entities
        if not matched_entities and all_entities:
            matched_entities = sorted(
                all_entities, 
                key=lambda e: e.last_updated or datetime.min.replace(tzinfo=timezone.utc), 
                reverse=True
            )[:3]

        if not matched_entities:
            return ""

        context_lines = ["[VERIFIED ENTITY FACTS]"]
        for ent in matched_entities:
            global_tag = " (Global Profile Fact)" if ent.is_global else ""
            context_lines.append(
                f"- {ent.name} ({ent.entity_type}){global_tag}: {ent.description}"
            )

        return "\n".join(context_lines)

    # Background Extraction: Discovers new entities via Groq, evolves existing descriptions (v1 -> v2), and records history
    async def update_memory(
        self, 
        conversation_id: str, 
        user_message: str, 
        assistant_message: str, 
        source_message_id: str,
        db: Session
    ) -> Dict[str, Any]:
        # Call Groq utility LLM to extract entities from the dialogue turn
        extraction = await llm_client.extract_entities_and_triples(
            user_message=user_message,
            assistant_message=assistant_message
        )

        extracted_entities = extraction.get("entities", [])
        if not extracted_entities:
            return {"memory_type": "entity", "extracted": 0}

        updated_count = 0
        new_count = 0

        # Mark source message as containing entity definitions (protects from middle-truncation)
        source_msg = db.query(Message).filter(Message.id == source_message_id).first()
        if source_msg:
            source_msg.has_entity_definition = True

        for item in extracted_entities:
            name = item.get("name", "").strip()
            ent_type = item.get("type", "other").strip()
            desc = item.get("description", "").strip()

            if not name or not desc:
                continue

            # Check if this entity already exists in this conversation
            existing = db.query(Entity).filter(
                Entity.conversation_id == conversation_id,
                Entity.name.ilike(name)
            ).first()

            if existing:
                # Evolve description: append new facts if not already present
                if desc.lower() not in existing.description.lower():
                    existing.description = f"{existing.description}; {desc}"
                existing.message_count += 1
                existing.last_updated = datetime.now(timezone.utc)
                
                # Record evolution snapshot in entity_history (v1 -> v2)
                new_version = len(existing.history) + 1
                history_entry = EntityHistory(
                    entity_id=existing.id,
                    version=new_version,
                    description_snapshot=existing.description,
                    source_message_id=source_message_id
                )
                db.add(history_entry)
                updated_count += 1
            else:
                # Insert newly discovered entity, stamped with its owner
                owner = db.query(Conversation.user_id).filter(Conversation.id == conversation_id).first()
                new_entity = Entity(
                    conversation_id=conversation_id,
                    user_id=owner[0] if owner else None,
                    name=name,
                    entity_type=ent_type,
                    description=desc,
                    message_count=1,
                    is_global=False
                )
                db.add(new_entity)
                db.flush()

                # Record version 1 snapshot in entity_history
                history_entry = EntityHistory(
                    entity_id=new_entity.id,
                    version=1,
                    description_snapshot=desc,
                    source_message_id=source_message_id
                )
                db.add(history_entry)
                new_count += 1

        db.commit()
        logger.info(f"Entity memory updated: {new_count} new, {updated_count} evolved.")
        return {
            "memory_type": "entity", 
            "new_entities": new_count, 
            "updated_entities": updated_count
        }

