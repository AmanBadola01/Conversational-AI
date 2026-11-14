import os
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.auth import get_current_user
from backend.app.core.database import get_db
from backend.app.models.db_models import Persona, User
from backend.app.models.schemas import PersonaCreate, PersonaResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personas", tags=["Personas"])

# Persona Seeder: Seeds the database with pre-configured personas from personas.json if the table is empty
def seed_default_personas(db: Session):
    count = db.query(Persona).count()
    if count > 0:
        return

    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "personas.json")
    if not os.path.exists(json_path):
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            persona = Persona(
                id=item["id"],
                name=item["name"],
                avatar=item.get("avatar", "🤖"),
                system_prompt=item["system_prompt"],
                personality=item.get("personality", ""),
                default_memory=item.get("default_memory", "buffer"),
                temperature=float(item.get("temperature", 0.7)),
                domain=item.get("domain", "general"),
                is_builtin=bool(item.get("is_builtin", True)),
                usage_count=0
            )
            db.add(persona)
        db.commit()
        logger.info(f"Seeded {len(data)} built-in personas from personas.json.")
    except Exception as e:
        logger.error(f"Error seeding default personas: {e}")
        db.rollback()

# List Personas: Retrieves all available personas ordered with built-in templates first followed by popularity
@router.get("", response_model=List[PersonaResponse])
def list_personas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ensure standard personas are populated on first launch
    seed_default_personas(db)

    personas = db.query(Persona).filter(
        (Persona.is_builtin == True) | (Persona.owner_id == current_user.id)
    ).order_by(
        desc(Persona.is_builtin),
        desc(Persona.usage_count),
        Persona.name.asc()
    ).all()

    return personas

# Get Persona Detail: Fetches complete configuration and system prompt for a single persona by ID
@router.get("/{persona_id}", response_model=PersonaResponse)
def get_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seed_default_personas(db)

    persona = db.query(Persona).filter(
        Persona.id == persona_id,
        (Persona.is_builtin == True) | (Persona.owner_id == current_user.id)
    ).first()
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Persona '{persona_id}' not found."
        )

    return persona

ALLOWED_MEMORY_TYPES = {"buffer", "summary", "entity", "kg", "hybrid"}

# Create Persona: Registers a user-defined custom AI personality with dedicated prompt and memory pairing
@router.post("", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
def create_persona(
    payload: PersonaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    normalized_id = payload.id.strip().lower()
    if payload.default_memory.strip().lower() not in ALLOWED_MEMORY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid default_memory '{payload.default_memory}'. Allowed: {sorted(ALLOWED_MEMORY_TYPES)}."
        )
    # Check for duplicate persona ID (ids are stored lowercased)
    existing = db.query(Persona).filter(Persona.id == normalized_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Persona with ID '{payload.id}' already exists."
        )

    new_persona = Persona(
        id=normalized_id,
        name=payload.name.strip(),
        avatar=payload.avatar.strip(),
        system_prompt=payload.system_prompt.strip(),
        personality=payload.personality.strip(),
        default_memory=payload.default_memory.strip().lower(),
        temperature=payload.temperature,
        domain=payload.domain.strip(),
        is_builtin=False,
        owner_id=current_user.id,
        usage_count=0
    )

    db.add(new_persona)
    db.commit()
    db.refresh(new_persona)

    return new_persona

# Delete Persona: Deletes a user-created custom persona while preventing deletion of core built-in templates
@router.delete("/{persona_id}", status_code=status.HTTP_200_OK)
def delete_persona(
    persona_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    persona = db.query(Persona).filter(
        Persona.id == persona_id,
        (Persona.owner_id == current_user.id)
    ).first()
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Persona '{persona_id}' not found."
        )

    # Disallow deleting core system personas
    if persona.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Built-in personas cannot be deleted."
        )

    db.delete(persona)
    db.commit()

    return {"status": "deleted", "persona_id": persona_id}
