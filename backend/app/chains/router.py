import logging
from typing import Dict, Any
from backend.app.llm.client import llm_client

logger = logging.getLogger(__name__)

# Intent Directives: Specific system prompt guidance tailored to classified user intents
INTENT_DIRECTIVES: Dict[str, str] = {
    "factual_recall": (
        "[Response Directive: Factual Recall]\n"
        "The user is asking about specific facts, entities, tech stacks, people, or details mentioned earlier. "
        "Ground your response strictly on the verified facts in the memory context. If uncertain, state what is known."
    ),
    "analysis": (
        "[Response Directive: Deep Analysis]\n"
        "The user is requesting an architectural review, comparison, strategic breakdown, or in-depth explanation. "
        "Provide a well-structured response evaluating trade-offs, advantages, and actionable recommendations."
    ),
    "instruction": (
        "[Response Directive: Direct Instruction]\n"
        "The user gave a specific task, coding prompt, or direct command. "
        "Execute the requested instruction cleanly and step-by-step with zero fluff."
    ),
    "small_talk": (
        "[Response Directive: Casual Conversation]\n"
        "The user is offering greetings, casual chatter, or light conversation. "
        "Respond warmly, naturally, and concisely without over-explaining."
    )
}

# Intent Classifier: Determines query intent using Groq utility LLM with rule-based fallback
async def route_intent(query: str) -> str:
    return await llm_client.classify_intent(query)

# Directive Resolver: Resolves and returns the targeted prompt modifier for the classified intent
def get_intent_directive(intent: str) -> str:
    return INTENT_DIRECTIVES.get(intent.lower(), INTENT_DIRECTIVES["small_talk"])

# Prompt Assembler: Combines persona system prompt, intent directive, and memory context block
def assemble_system_prompt(base_prompt: str, intent: str, memory_context: str) -> str:
    sections = [base_prompt.strip()]
    
    # Append dynamic intent directive
    directive = get_intent_directive(intent)
    sections.append(directive)

    # Append active memory context if available
    if memory_context.strip():
        sections.append(memory_context.strip())

    return "\n\n".join(sections)
