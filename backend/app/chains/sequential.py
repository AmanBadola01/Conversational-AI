import logging
from typing import Dict, Any, List, AsyncIterator, Tuple, Optional
from sqlalchemy.orm import Session
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from backend.app.models.db_models import Conversation, Message, Persona
from backend.app.memory.manager import memory_manager
from backend.app.chains.router import route_intent, assemble_system_prompt
from backend.app.core.context_manager import context_manager, count_tokens
from backend.app.llm.client import llm_client

logger = logging.getLogger(__name__)

# Context Builder: Fetches conversation state, resolves persona, and applies Smart Middle-Truncation within the token budget
def prepare_chain_context(
    conversation_id: str, 
    user_query: str, 
    db: Session
) -> Dict[str, Any]:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} not found.")

    # Resolve active persona (fallback to General Assistant default if unassigned)
    persona = None
    if conversation.persona_id:
        persona = db.query(Persona).filter(Persona.id == conversation.persona_id).first()
    
    base_system_prompt = (
        persona.system_prompt if persona else 
        "You are a helpful, versatile AI conversational partner."
    )
    temperature = persona.temperature if persona else 0.7

    # Retrieve all historical messages ordered chronologically
    all_messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    # Apply Smart Middle-Truncation against recent messages budget (1,500 tokens)
    truncated_messages, was_truncated, pruned_count = context_manager.smart_middle_truncate(
        messages=all_messages,
        max_tokens=context_manager.recent_budget
    )

    # Fetch active memory context (including any pre-switch summary)
    memory_context = memory_manager.get_context(
        conversation=conversation, 
        current_query=user_query, 
        db=db
    )

    return {
        "conversation": conversation,
        "persona": persona,
        "base_system_prompt": base_system_prompt,
        "temperature": temperature,
        "memory_context": memory_context,
        "truncated_messages": truncated_messages,
        "was_truncated": was_truncated,
        "pruned_count": pruned_count
    }

# Message Formatter: Converts database history into LangChain message objects with injected system directives
def format_messages_for_llm(
    system_prompt: str, 
    history_messages: List[Message], 
    current_query: str
) -> List[BaseMessage]:
    formatted: List[BaseMessage] = [SystemMessage(content=system_prompt)]

    for msg in history_messages:
        if msg.role == "user":
            formatted.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            formatted.append(AIMessage(content=msg.content))

    formatted.append(HumanMessage(content=current_query))
    return formatted

# Pipeline Orchestrator: Executes the end-to-end sequential LCEL chain and streams tokens from Gemini
async def execute_sequential_chain(
    conversation_id: str, 
    user_query: str, 
    db: Session
) -> Tuple[AsyncIterator[str], Dict[str, Any]]:
    # Step 1: Prepare context, truncate history, and fetch memory
    ctx = prepare_chain_context(conversation_id, user_query, db)

    # Step 2: Classify intent via router (factual_recall, analysis, instruction, small_talk)
    intent = await route_intent(user_query)

    # Step 3: Assemble dynamically routed system prompt with intent modifier and memory block
    full_system_prompt = assemble_system_prompt(
        base_prompt=ctx["base_system_prompt"],
        intent=intent,
        memory_context=ctx["memory_context"]
    )

    # Step 4: Calculate real-time token breakdown for UI telemetry
    token_audit = context_manager.calculate_token_breakdown(
        system_prompt=full_system_prompt,
        memory_context=ctx["memory_context"],
        messages=ctx["truncated_messages"],
        conversation_id=conversation_id
    )

    # Step 5: Format messages for Gemini LLM
    llm_messages = format_messages_for_llm(
        system_prompt=full_system_prompt,
        history_messages=ctx["truncated_messages"],
        current_query=user_query
    )

    # Metadata payload for API and frontend telemetry
    metadata = {
        "conversation_id": conversation_id,
        "intent": intent,
        "memory_type": ctx["conversation"].memory_type,
        "was_truncated": ctx["was_truncated"],
        "pruned_count": ctx["pruned_count"],
        "token_audit": token_audit
    }

    # Step 6: Create async token stream from Gemini
    token_stream = llm_client.astream_chat(
        messages=llm_messages,
        temperature=ctx["temperature"]
    )

    return token_stream, metadata

# Background Persister: Saves dialogue turn to PostgreSQL and triggers background memory updates
async def post_turn_update(
    conversation_id: str, 
    user_message: str, 
    assistant_message: str, 
    db: Session
) -> Dict[str, Any]:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        return {"status": "error", "message": f"Conversation {conversation_id} not found."}

    user_token_count = count_tokens(user_message)
    asst_token_count = count_tokens(assistant_message)

    # Persist user message
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=user_message,
        token_count=user_token_count
    )
    db.add(user_msg)
    db.flush()

    # Persist assistant message
    asst_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_message,
        token_count=asst_token_count
    )
    db.add(asst_msg)
    db.commit()

    # Trigger post-turn memory update (summary condensation, entity evolution, or KG triples extraction)
    memory_update_result = await memory_manager.update(
        conversation=conversation,
        user_message=user_message,
        assistant_message=assistant_message,
        source_message_id=user_msg.id,
        db=db
    )

    return {
        "status": "success",
        "user_message_id": user_msg.id,
        "assistant_message_id": asst_msg.id,
        "memory_update": memory_update_result
    }
