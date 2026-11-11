import logging
import json
import re
import asyncio
from typing import AsyncIterator, List, Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Dual-LLM Client Architecture:
    1. Primary LLM: Google Gemini (High-reasoning, real-time streaming chat responses)
    2. Utility LLM: Groq (Ultra-fast, handles background extraction & summarization)
    """

    def __init__(self):
        self._primary_chat_llm = None
        self._utility_llm = None
        self._init_clients()

    # Initialization: Configures Gemini for Primary Chat and Groq for Utility tasks
    def _init_clients(self):
        # 1. Primary LLM: Google Gemini
        if settings.GEMINI_API_KEY:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._primary_chat_llm = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL,
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.7,
                    streaming=True
                )
                logger.info(f"Primary LLM initialized with Gemini ({settings.GEMINI_MODEL})")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini Primary LLM: {e}")
        else:
            logger.warning("GEMINI_API_KEY not set. Primary LLM running in mock/demo mode.")

        # 2. Utility LLM: Groq (Llama-3.1-8b)
        if settings.GROQ_API_KEY:
            try:
                from langchain_groq import ChatGroq
                self._utility_llm = ChatGroq(
                    model=settings.GROQ_MODEL,
                    groq_api_key=settings.GROQ_API_KEY,
                    temperature=0.1
                )
                logger.info(f"Utility LLM initialized with Groq ({settings.GROQ_MODEL})")
            except Exception as e:
                logger.error(f"Failed to initialize Groq Utility LLM: {e}")
        elif settings.GEMINI_API_KEY:
            # Fallback to Gemini if Groq key is not configured
            logger.info("Using Gemini as fallback Utility LLM.")
            self._utility_llm = self._primary_chat_llm

    # Primary Chat: Returns a fresh Gemini instance with persona-specific temperature
    def get_primary_llm(self, temperature: float = 0.7):
        if self._primary_chat_llm and settings.GEMINI_API_KEY:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=temperature,
                streaming=True
            )
        return None

    # Utility Engine: Returns the Groq client for background memory extraction
    def get_utility_llm(self):
        return self._utility_llm

    # Real-Time Chat: Asynchronously streams token chunks via Server-Sent Events (SSE)
    async def astream_chat(
        self, 
        messages: List[BaseMessage], 
        temperature: float = 0.7
    ) -> AsyncIterator[str]:
        llm = self.get_primary_llm(temperature=temperature)
        if llm:
            try:
                async for chunk in llm.astream(messages):
                    if hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
                return
            except Exception as e:
                logger.error(f"Error streaming from Gemini: {e}")
                yield f"[API Error: {e}]"
                return

        # Development Fallback Streamer (runs when GEMINI_API_KEY is not yet supplied)
        mock_response = (
            "Hello! I am operating in development preview mode. "
            "Please add your `GEMINI_API_KEY` into `backend/.env` to enable live streaming. "
            "Your prompt and memory context were successfully formatted."
        )
        for word in mock_response.split(" "):
            await asyncio.sleep(0.04)
            yield word + " "

    # Memory Technique: Batch Extraction for Entity Memory & Knowledge Graph Memory
    async def extract_entities_and_triples(
        self, 
        user_message: str, 
        assistant_message: str
    ) -> Dict[str, Any]:
        prompt = f"""
You are an advanced knowledge and entity extraction engine.
Analyze the following conversation turn between a User and Assistant.

Conversation Turn:
User: {user_message}
Assistant: {assistant_message}

Tasks:
1. Extract meaningful entities (people, organizations, projects, technologies, dates, key concepts).
   - Exclude generic words like 'hello', 'question', 'bot', 'answer', 'user'.
   - For each entity, specify its exact name, category ('person', 'organization', 'project', 'technology', 'date', 'concept', 'other'), and a factual description.
2. Extract meaningful Knowledge Graph relationships as (subject, predicate, object) triples.
   - Exclude trivial statements like ('user', 'said', 'hello').
   - Triples must represent real facts (e.g. 'Alice', 'manages', 'Project X' or 'Project X', 'uses', 'FastAPI').

Output strictly in valid JSON format with this exact structure:
{{
  "entities": [
    {{"name": "...", "type": "...", "description": "..."}}
  ],
  "triples": [
    {{"subject": "...", "predicate": "...", "object": "..."}}
  ]
}}
"""
        if self._utility_llm:
            try:
                res = await self._utility_llm.ainvoke([HumanMessage(content=prompt)])
                content = res.content if hasattr(res, "content") else str(res)
                # Strip markdown code fences if present
                clean_json = re.sub(r"^```json\s*|\s*```$", "", content.strip(), flags=re.MULTILINE)
                return json.loads(clean_json)
            except Exception as e:
                logger.warning(f"Utility LLM extraction failed: {e}. Falling back to rule-based parser.")
        
        # Rule-based fallback extraction if utility LLM is offline
        return self._heuristic_extraction(user_message)

    # Heuristic Fallback: Rule-based entity & triple parser when offline
    def _heuristic_extraction(self, text: str) -> Dict[str, Any]:
        entities = []
        triples = []
        words = text.split()
        for w in words:
            clean_w = w.strip(",.!?\"'")
            if clean_w.istitle() and len(clean_w) > 3 and clean_w.lower() not in {"what", "when", "where", "how", "this", "that"}:
                entities.append({
                    "name": clean_w,
                    "type": "concept",
                    "description": f"Mentioned in context: '{text[:80]}...'"
                })
        return {"entities": entities[:3], "triples": triples}

    # Memory Technique: Summary Memory (compresses conversation turns into a condensed macro-summary)
    async def summarize_conversation(
        self, 
        current_summary: str, 
        new_messages: List[Any]
    ) -> str:
        msg_text = "\n".join([f"{getattr(m, 'role', 'user')}: {getattr(m, 'content', '')}" for m in new_messages])
        prompt = f"""
Condense the following conversation history into a structured, concise paragraph.
Preserve key facts, decisions, requirements, and decisions made.
Do not lose critical technical details, names, or deadlines.

Previous Summary (if any):
{current_summary or 'None'}

New Messages to incorporate:
{msg_text}

Provide only the updated condensed summary paragraph:
"""
        if self._utility_llm:
            try:
                res = await self._utility_llm.ainvoke([HumanMessage(content=prompt)])
                return res.content.strip() if hasattr(res, "content") else str(res).strip()
            except Exception as e:
                logger.error(f"Summarization error: {e}")
        
        return f"Summary of {len(new_messages)} messages: Key technical and project requirements discussed."

    # LangChain LCEL Routing: Classifies message intent (factual_recall, analysis, instruction, small_talk)
    async def classify_intent(self, message: str) -> str:
        prompt = f"""
Classify the following user message into exactly ONE of these four categories:
1. 'factual_recall' (asking about a specific fact, deadline, person, tech stack, or detail mentioned earlier)
2. 'analysis' (asking for a comparison, architectural review, strategic breakdown, or essay)
3. 'instruction' (giving a command or task, e.g. 'write a function', 'change the config')
4. 'small_talk' (casual greetings, brief chit-chat, hello, thanks)

User Message: "{message}"

Respond with ONLY the category name.
"""
        if self._utility_llm:
            try:
                res = await self._utility_llm.ainvoke([HumanMessage(content=prompt)])
                intent = res.content.strip().lower().replace("'", "").replace('"', '')
                for category in ["factual_recall", "analysis", "instruction", "small_talk"]:
                    if category in intent:
                        return category
            except Exception:
                pass
        
        # Rule-based intent fallback
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["who", "what is", "when", "deadline", "recall", "remember"]):
            return "factual_recall"
        if any(w in msg_lower for w in ["compare", "analyze", "why", "strategy", "overview"]):
            return "analysis"
        if any(w in msg_lower for w in ["hi", "hello", "hey", "thanks", "bye"]):
            return "small_talk"
        return "instruction"

llm_client = LLMClient()
