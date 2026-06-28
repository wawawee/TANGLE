# TANGLE

> **The world is tangled. Information is tangled. Problems are tangled. We exist to untangle.**

TANGLE is an entity assistance intelligence. Drop a file. Name an entity — a person, a cat, a company, a project team. TANGLE autonomously parses the file, vectorizes the content, builds a structured wiki, and synthesizes a coherent markdown report describing concrete ways to help that entity.

**Phase 0: The Skeleton** — the working pipeline runs end-to-end. File drop → parse → vectorize → agent loop → markdown report → radiating wiki graph.

---

## Quick start

```bash
# 1. Start Qdrant (vector store)
docker-compose up -d

# 2. Backend (FastAPI on port 8000)
cd backend
source venv/bin/activate
pip install -r requirements.txt
python main.py

# 3. Frontend (Vite on port 5173)
cd frontend
npm install
npm run dev

# 4. Open http://localhost:5173
# 5. Drop a PDF / TXT, type "Help [Entity Name]", press Enter.
```

Requires:
- Docker (Qdrant)
- Python 3.11+
- Node 20+
- One of: `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, or local Ollama running

---

## Project structure

```
TANGLE/
├── backend/                  # FastAPI app (Python)
│   ├── main.py               # All HTTP endpoints
│   ├── agent_orchestrator.py # Mission loop: plan → scout → librarian → critic → synthesize
│   ├── parsing_engine.py     # File → markdown (markitdown + vision dual-pass)
│   ├── vector_store.py       # SQLite + Qdrant dual-store, embeddings
│   ├── free_gateway.py       # Multi-provider LLM router (OpenRouter → Gemini → Ollama)
│   ├── task_manager.py       # In-app TASKLIST.md source-of-truth
│   ├── kanban_store.py       # Per-task kanban columns
│   ├── run_history.py        # Agent-run audit trail
│   ├── review_harness.py     # 3-persona self-review (debugger / senior / user)
│   ├── review_agent_prompt.md # Prompt driving the review harness
│   ├── langgraph_engine.py   # LangGraph state machine (used in `/api/agents/lg/execute`)
│   ├── browser_agent.py      # browser-use integration
│   └── archon_integration.py # Archon workflow wrappers
├── frontend/                 # Vite + React + TypeScript
│   └── src/
│       ├── App.tsx           # Mission card + React Flow canvas + side panels
│       ├── components/       # FileDropZone, KanbanBoard, NodeInspector, RunHistory, TaskListPanel, ChatBox, CliHarness, AgentVerbosePanel, Experience3D
│       ├── nodes/            # SourceNode, EntityNode, WikiNode (React Flow node types)
│       ├── store/agentStore.ts # Zustand store: WS, uploadFile, startMission, telemetry
│       └── index.css         # Dark glass tokens, mesh, animations
├── docker-compose.yml        # Qdrant only
├── scripts/                  # Bootstrap helpers
└── archive/                  # Archived legacy (SAMI/ARKITEKT/NULLCLAW era)
```

---

## Wiki Markdown Spec

Every parsed chunk follows this structure. Frontend and downstream tools parse on these headings.

```markdown
# Entity: [Name]
## Source: [Filename]
### Extracted: [ISO Timestamp]
### Confidence: [0.00–1.00]
### Chunk ID: [uuid]

[Raw content from source file...]

### Related Chunks
- [[vector-link-uuid]]
- [[source-file-link]]

### Tags
- #health #finance #legal #contact #risk
```

---

## Principles (non-negotiable)

- **Peu un peu.** Little by little. If it doesn't fit Phase 0, it goes in the "Later" bucket.
- **Cost is a feature.** Default to the cheapest model that works. Premium (Claude / GPT-4o) only for complex tasks.
- **Source everything.** Every claim has a citation. Every extraction has a confidence score.
- **Markdown is king.** All data flows as markdown. The wiki format above is the standard.
- **No law DBs.** We verify via the web. No static legal libraries.

---

## Phase 0 success metric

> User drops a PDF about "Acme Corp". Types "Help Acme Corp". TANGLE returns a coherent markdown report with concrete suggestions on how to help the company, sourced from the file + simple AI reasoning.

If this works, Phase 0 breathes.

---

## Tech stack

| Layer       | Choice                                    |
|-------------|-------------------------------------------|
| Frontend    | Vite + React 19 + TypeScript + React Flow |
| Backend     | FastAPI (Python 3.11+)                    |
| Vector DB   | Qdrant (self-hosted via docker-compose)   |
| Relational  | SQLite (fallback), Supabase (planned)     |
| LLM         | OpenRouter (free tier) → Gemini → Ollama  |
| File parse  | markitdown, pandoc, unstructured          |

Later: Next.js 14 (frontend), Supabase + auth, Redis + Celery for task queue.
