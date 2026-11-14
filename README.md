# Continuum — Conversational AI

A full-stack AI chat workspace with persistent conversations, configurable personas, and inspectable memory. Continuum combines streamed responses with summaries, entity tracking, and knowledge graphs to carry useful context across longer conversations.

**[Open the live app](http://agents.excellencetechnologies.in:20311/)** · **[Sign in / Create an account](http://agents.excellencetechnologies.in:20311/login/)**

## Features

- **Streaming chat:** Gemini responses delivered through Server-Sent Events, with saved conversation history.
- **Account-based workspace:** registration, sign-in, password hashing, and ownership checks for conversations and personal resources.
- **Conversation management:** rename, pin, archive, and export conversations.
- **Five memory strategies:** buffer, summary, entity, knowledge graph, and hybrid, with automatic buffer-to-hybrid switching for longer chats.
- **Memory inspection:** explore extracted entities, entity history, relationship triples, summaries, and context usage.
- **Configurable personas:** built-in assistants and custom personas with their own instructions and default memory settings.
- **Context budgeting:** a configurable 4,000-token budget with middle truncation that prioritizes initial context, entity-defining messages, and recent turns.
- **Responsive interface:** light/dark themes, a React message composer, and animated topology backgrounds that respect reduced-motion preferences.

## Technology

| Layer | Stack |
| --- | --- |
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS 4 |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| AI orchestration | LangChain, Google Gemini, Groq |
| Persistence | PostgreSQL, with a local SQLite fallback |
| Streaming | Server-Sent Events (SSE) |
| Deployment | Uvicorn, PM2; one origin for the UI and API |

Gemini generates user-facing replies. Groq handles utility work such as summarization and fact extraction. The integrated server defaults to `gemini-3.1-flash-lite` and `openai/gpt-oss-20b`; both model names can be overridden through environment variables.

## How it works

1. An authenticated user opens a conversation and selects a persona and memory strategy.
2. The backend assembles persona instructions, retrieved memory, and recent messages within the context budget.
3. The selected chain streams the model response to the browser.
4. Conversation turns are persisted, and the memory pipeline updates summaries, entities, or relationships according to the selected strategy.
5. The inspector exposes the stored memory for review.

## Run locally

### Requirements

- Python 3.10 or newer.
- Node.js 22.12 or newer and npm.
- Gemini and Groq API credentials for the full AI workflow.
- PostgreSQL for a managed database, or the built-in SQLite fallback for local development.

### 1. Clone and install

```bash
git clone https://github.com/AmanBadola01/Conversational-AI.git
cd Conversational-AI
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

On Windows, activate the environment with `.venv\Scripts\activate`.

### 2. Configure the backend

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` with your database URL, API credentials, and a long random `AUTH_SECRET`. The file is excluded from Git.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection URL. If PostgreSQL is unavailable, the app falls back to `conversational_ai.db` in the working directory. |
| `GEMINI_API_KEY` | Primary chat provider credential. |
| `GROQ_API_KEY` | Utility provider credential for memory tasks. |
| `GEMINI_MODEL` | Optional primary model override. |
| `GROQ_MODEL` | Optional utility model override. |
| `AUTH_SECRET` | Stable signing secret for login tokens; configure it for persistent sessions across restarts. |
| `DEBUG` | Set to `False` for deployment. |

Managed deployments also accept injected `SECRET_GEMINI_API_KEY` and `SECRET_GROQ_API_KEY` values. Keep all credentials on the server.

### 3. Build the interface

```bash
cd frontend-preview
npm ci
npm run build:integrated
cd ..
```

This compiles the chat interface and login background, then assembles the integrated page in `frontend-preview/dist/`.

### 4. Start the application

From the repository root, with the Python virtual environment active:

```bash
uvicorn preview_server:app --host 127.0.0.1 --port 8000
```

Open **http://localhost:8000/** and create an account. The integrated server serves both the frontend and API.

| Route | Purpose |
| --- | --- |
| `/` | Chat workspace |
| `/login/` | Sign-in and registration |
| `/docs` | Interactive API documentation |
| `/health` | Application and database health |
| `/api/runtime` | Model names and provider configuration status; no credentials |

To run only the API, use `uvicorn backend.app.main:app --host 127.0.0.1 --port 8000`.

## Tests

From the repository root with the virtual environment active:

```bash
python -m unittest backend.tests.test_backend_regressions -v
```

Frontend tests and production build:

```bash
cd frontend-preview
npm test
npm run build:integrated
```

For integration tests against a running local server:

```bash
PREVIEW_URL=http://127.0.0.1:8000 npm run test:live
```

The live suite exercises real HTTP APIs and may call configured model providers. Use a development instance for this check.

## Repository layout

```text
backend/
  app/
    chains/          Intent routing and sequential orchestration
    core/            Configuration, authentication, database, context budget
    data/            Built-in persona definitions
    llm/             Gemini and Groq clients
    memory/          Buffer, summary, entity, graph, and hybrid strategies
    models/          Database models and request/response schemas
    routers/         Authentication, conversations, messages, memory, personas
  tests/             Backend regression tests
  .env.example       Environment template
  requirements.txt   Python dependencies
frontend-preview/
  components/        React interface components
  scripts/           Builds and frontend/integration tests
  integrated.js      Browser-to-backend integration
  index.html         Workspace template
login/               Login page, styles, and background assets
deploy/              PM2 configuration and deployment notes
preview_server.py    Integrated frontend/API entry point
```

## Deployment notes

The current live instance is served at [agents.excellencetechnologies.in:20311](http://agents.excellencetechnologies.in:20311/). See [deployment instructions](deploy/README.md) for PM2 commands and host reboot recovery requirements.

Use HTTPS and a persistent `AUTH_SECRET` for an internet-facing deployment. The current live address uses HTTP. Back up the database separately; credentials, database files, dependencies, and process state are excluded from source control. PM2 crash recovery is configured; host reboot recovery still requires administrator setup.

The standalone frontend preview simulates chat; run `preview_server:app` for real backend integration. Chat accepts text only; image upload and analysis are not implemented. Voice transcription depends on browser support and a secure context.

## Author

Built by [Aman Badola](https://github.com/AmanBadola01).
