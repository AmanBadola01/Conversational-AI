import json
import logging
from typing import List, AsyncIterator, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.app.core.auth import get_current_user, get_owned_conversation
from backend.app.core.database import get_db, SessionLocal
from backend.app.models.db_models import Conversation, Message, ConversationSummary, User
from backend.app.models.schemas import MessageCreate, MessageResponse
from backend.app.chains.sequential import execute_sequential_chain, post_turn_update

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["Messages"])

# Event Stream Generator: Streams token chunks, emits live telemetry metadata, and triggers background persistence
async def stream_chat_turn(
    conversation_id: str, 
    user_query: str, 
    db: Session
) -> AsyncIterator[str]:
    # Step 1: Execute the sequential LCEL chain to obtain the token stream and turn metadata
    token_stream, metadata = await execute_sequential_chain(
        conversation_id=conversation_id,
        user_query=user_query,
        db=db
    )

    # Step 2: Emit initial metadata event (intent, memory type, token audit, truncation status)
    yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"

    # Step 3: Stream generated response tokens in real-time as they are yielded from Gemini
    accumulated_tokens = []
    try:
        async for token_chunk in token_stream:
            accumulated_tokens.append(token_chunk)
            yield f"data: {json.dumps({'type': 'token', 'token': token_chunk})}\n\n"
    except Exception as e:
        logger.error(f"Streaming error for conversation {conversation_id}: {e}")
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        return

    # Step 4: After streaming finishes, save the dialogue turn and trigger background memory extraction
    assistant_full_reply = "".join(accumulated_tokens)
    bg_db = SessionLocal()
    try:
        post_update_result = await post_turn_update(
            conversation_id=conversation_id,
            user_message=user_query,
            assistant_message=assistant_full_reply,
            db=bg_db
        )
        yield f"data: {json.dumps({'type': 'done', 'data': post_update_result})}\n\n"
    except Exception as e:
        logger.error(f"Post-turn memory update failed for conversation {conversation_id}: {e}")
        yield f"data: {json.dumps({'type': 'done', 'error': str(e)})}\n\n"
    finally:
        bg_db.close()

# Send Message: Accepts user input and returns real-time streaming response via Server-Sent Events (SSE)
@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    # Return persistent Server-Sent Events (SSE) stream
    return StreamingResponse(
        stream_chat_turn(
            conversation_id=conversation_id,
            user_query=payload.content,
            db=db
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# List Messages: Retrieves all messages for a conversation ordered chronologically
@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def list_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    return messages

# Clear Messages: Clears all dialogue turns from a conversation while preserving settings and persona
@router.delete("/{conversation_id}/messages", status_code=status.HTTP_200_OK)
def clear_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    deleted_count = db.query(Message).filter(Message.conversation_id == conversation_id).delete()
    # A cleared chat must not keep injecting its old summary as context.
    db.query(ConversationSummary).filter(
        ConversationSummary.conversation_id == conversation_id
    ).delete()
    conv.pre_switch_summary = None
    db.commit()

    return {
        "status": "cleared",
        "conversation_id": conversation_id,
        "deleted_messages_count": deleted_count
    }
