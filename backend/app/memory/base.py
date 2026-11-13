from abc import ABC, abstractmethod
from typing import Dict, Any
from sqlalchemy.orm import Session

class BaseMemory(ABC):
    """
    Abstract Base Class for all Memory Strategies in the Platform.
    Enforces a consistent polymorphic interface across:
    - BufferMemory
    - SummaryMemory
    - EntityMemory
    - KGMemory
    - HybridMemory
    """

    # Constructor: Initializes the memory strategy with its unique type identifier (e.g. buffer, summary, entity, kg, hybrid)
    def __init__(self, memory_type: str):
        self.memory_type = memory_type

    # Prompt Injection: Formats and returns the memory context string to be injected into the LLM system prompt
    @abstractmethod
    def get_memory_context(
        self, 
        conversation_id: str, 
        current_query: str, 
        db: Session
    ) -> str:
        """
        Retrieves relevant memory state from the database and formats it into a prompt context block.
        """
        pass

    # State Mutation: Updates internal memory tables (entities, graph triples, summaries) in PostgreSQL following a chat turn
    @abstractmethod
    async def update_memory(
        self, 
        conversation_id: str, 
        user_message: str, 
        assistant_message: str, 
        source_message_id: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Executed in the background after each turn to extract facts, update summaries, or prune history.
        """
        pass

