# Conversational AI Platform with Memory & Chains

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-336791.svg)](https://www.postgresql.org/)
[![LangChain](https://img.shields.io/badge/Orchestration-LangChain%20LCEL-1C3C3C.svg)](https://python.langchain.com/)
[![Gemini](https://img.shields.io/badge/Primary%20LLM-Google%20Gemini-4285F4.svg)](https://ai.google.dev/)
[![Groq](https://img.shields.io/badge/Utility%20LLM-Groq%20Llama--3.1-F55036.svg)](https://groq.com/)

An enterprise-grade Conversational AI Platform engineered to solve the hardest challenge in production chatbots: **stateful memory, long-term factual recall, and context window optimization**.

---

## 🎯 The Core Problem & Mission

Standard chatbots suffer from **naive memory**: they append the entire raw chat history into every prompt. This causes:
1. **$O(N)$ Token Explosion**: Conversations quickly breach token limits, generating costly API errors.
2. **Context Dilution ("Lost in the Middle")**: Crucial facts established early in the conversation are forgotten or hallucinated away.
3. **Naive Truncation Flaws**: Traditional FIFO truncation drops the oldest messages first, immediately erasing the original setup instructions and project constraints.

### The Ultimate Benchmark
> *"Can your chatbot maintain a 50+ message conversation and accurately recall a specific fact introduced in Message #3 when queried at Message #50 without running out of tokens?"*

This platform achieves this through **4 discrete memory paradigms**, a **composite hybrid engine**, **modern LangChain LCEL chains**, and **Smart Middle-Truncation**.

---

## 🧠 Architectural Pillars

```text
                                  ┌─────────────────────────────┐
                                  │      Incoming Message       │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │  Intent Classifier & Router │
                                  └──────────────┬──────────────┘
                                                 │
                   ┌─────────────────────────────┼─────────────────────────────┐
                   │                             │                             │
                   ▼                             ▼                             ▼
       ┌───────────────────────┐     ┌───────────────────────┐     ┌───────────────────────┐
       │     Summary Memory    │     │     Entity Memory     │     │  Knowledge Graph (KG) │
       │  • Periodic macro-    │     │  • Micro-fact store   │     │  • (Subject, Predicate│
       │    condensation every │     │  • Attribute tracking │     │    Object) triples    │
       │    N turns (default 5)│     │  • Version timeline   │     │  • Relational sub-    │
       │  • O(1) token cost    │     │    (v1 -> v2 -> v3)   │     │    graph queries      │
       └───────────┬───────────┘     └───────────┬───────────┘     └───────────┬───────────┘
                   │                             │                             │
                   └─────────────────────────────┼─────────────────────────────┘
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    Hybrid Memory Context    │
                                  │ Summary + Entities + Graph  │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │   Context Window Manager    │
                                  │  • 4,000 Total Token Budget │
                                  │  • Smart Middle-Truncation  │
                                  └──────────────┬──────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    Primary LLM (Gemini)     │
                                  │  Streaming Response via SSE │
                                  └─────────────────────────────┘
```

### 1. The 5 Memory Paradigms
- **Buffer Memory (`ConversationBufferMemory`)**: Stores exact dialogue verbatim. Ideal for short, highly focused interactions ($< 20$ messages).
- **Summary Memory (`ConversationSummaryMemory`)**: Condenses older dialogue into a concise running summary paragraph every $N$ messages (default: 5) using an LLM.
- **Entity Memory (`ConversationEntityMemory`)**: Extracts named entities (people, projects, organizations, technologies, dates), dynamically updates their attributes, and maintains a versioned timeline ($v_1 \to v_2 \to v_3$).
- **Knowledge Graph Memory (`ConversationKGMemory`)**: Extracts Subject-Predicate-Object triples `(Subject, Predicate, Object)` and queries connected subgraphs for relationship context.
- **Hybrid Memory & Auto-Switching Engine**: Combines Summary (macro) + Entity (micro) + KG (relational) + recent buffer turns. Automatically upgrades conversations from Buffer to Hybrid once history exceeds 15 messages.

### 2. Context Window Economics & Smart Middle-Truncation
Strictly manages a **4,000-token total budget**:
- **System / Persona Prompt**: 500 tokens
- **Memory Context (Summary + Entities + KG)**: 1,000 tokens
- **Recent Messages Window**: 1,500 tokens
- **Reserved Output Buffer**: 1,000 tokens

**Smart Middle-Truncation Algorithm**:
Instead of dropping the oldest messages (which erases early instructions and setup parameters), it prunes from the **middle** of dialogue history while strictly preserving:
1. **The Head Anchor**: Initial setup messages and guidelines.
2. **Entity-Defining Messages**: Any message where entities or facts were first declared (`has_entity_definition = True`).
3. **The Tail Anchor**: The latest user prompt and immediate conversational turns.

### 3. Dual-LLM Infrastructure
To avoid rate-limit exhaustion (`HTTP 429`) on free-tier APIs:
- **Primary LLM (Google Gemini 2.0 Flash)**: Reserved strictly for real-time user-facing conversational streaming via Server-Sent Events (SSE).
- **Utility LLM (Groq Llama-3.1-8b)**: Operates at ~500 tokens/sec to execute background tasks (entity extraction, KG triple discovery, periodic summarization) in parallel without blocking user streaming.

---

## 🗄️ Database Architecture (PostgreSQL + SQLAlchemy)

The database schema is modeled with full foreign-key constraints and cascading lifecycle management:

| Table | Purpose |
| :--- | :--- |
| **`conversations`** | Tracks chat sessions, active persona, memory strategy, and pin/archive status. |
| **`messages`** | Stores every dialogue turn verbatim, token counts, and entity definition markers. |
| **`entities`** | Dynamic fact store for subjects, supporting cross-session memory (`is_global`). |
| **`entity_history`** | Version snapshots ($v_1 \to v_2$) powering the Entity Evolution Timeline. |
| **`kg_triples`** | Relational facts powering the interactive network visualizer. |
| **`conversation_summaries`** | Running condensed macro-summaries of the dialogue. |
| **`personas`** | Chatbot personas (General Assistant, Code Helper, Creative Writer, Business Analyst, Study Buddy). |

---

## 📂 Project Structure

```text
Conversational AI/
├── backend/
│   ├── app/
│   │   ├── core/                  # Core configs, DB engine, Token Manager
│   │   │   ├── config.py          # Environment settings & budget constants
│   │   │   ├── database.py        # PostgreSQL engine & session factory
│   │   │   └── context_manager.py # 4k Budget & Smart Middle-Truncation
│   │   │
│   │   ├── memory/                # 🧠 Dedicated Isolated Memory Module
│   │   │   ├── base.py            # BaseMemory abstract interface
│   │   │   ├── buffer.py          # Verbatim buffer memory
│   │   │   ├── summary.py         # Condensed summary memory
│   │   │   ├── entity.py          # Entity memory & evolution store
│   │   │   ├── knowledge_graph.py # Subject-Predicate-Object triple engine
│   │   │   ├── hybrid.py          # Composite memory & auto-switching
│   │   │   └── manager.py         # Memory factory dispatcher
│   │   │
│   │   ├── chains/                # LangChain LCEL Pipelines
│   │   │   ├── sequential.py      # Intent -> Enrich -> Generate -> Update
│   │   │   ├── parallel.py        # Concurrent response + background extraction
│   │   │   └── router.py          # Dynamic intent routing
│   │   │
│   │   ├── llm/                   # Dual-LLM Clients
│   │   │   └── client.py          # Gemini Primary + Groq Utility setup
│   │   │
│   │   ├── models/                # Database Models & Pydantic Schemas
│   │   │   ├── db_models.py       # SQLAlchemy tables
│   │   │   └── schemas.py         # Request/response validation
│   │   │
│   │   ├── routers/               # FastAPI Endpoints
│   │   │   ├── conversations.py   # Conversation CRUD, Pin, Archive, Export
│   │   │   ├── messages.py        # Real-time SSE streaming chat
│   │   │   ├── memory.py          # Entity & Knowledge Graph inspection
│   │   │   ├── personas.py        # Persona configuration & testing
│   │   │   └── compare.py         # A/B Memory Comparison Workbench
│   │   │
│   │   ├── data/
│   │   │   └── personas.json      # 5 Built-in persona definitions
│   │   └── main.py                # FastAPI Application Entry
│   │
│   ├── requirements.txt           # Python dependencies
│   ├── .env.example               # Template environment configuration
│   └── test_backend.py            # Comprehensive verification test suite
│
├── .gitignore
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- PostgreSQL (or local SQLite fallback during setup)
- Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/))
- Groq API Key ([Groq Console](https://console.groq.com/))

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/AmanBadola01/Conversational-AI.git
cd Conversational-AI

# Create and activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Configure `.env`
Copy the example configuration:
```bash
cp backend/.env.example backend/.env
```
Fill in your credentials in `backend/.env`:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/conversational_ai
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

### 4. Run the Backend Server
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive Swagger documentation is available at: **`http://localhost:8000/docs`**

---

## 🧪 Verification & Automated Testing

To run the complete verification suite verifying database connectivity, persona initialization, middle-truncation, and streaming:
```bash
python backend/test_backend.py
```

---

## 👤 Author
- **Aman Badola** - [GitHub](https://github.com/AmanBadola01)
