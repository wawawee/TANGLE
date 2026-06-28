# TANGLE — Free-Tier API Keys Checklist

Generated 2026-06-28 by Mavis. Use this when signing up for new data sources tomorrow.

**Conventions**
- ✅ = already have / in `.env` (just rotate periodically)
- 🟡 = sign up tomorrow
- 🔵 = no key required, just configure endpoint
- ❌ = skipped (ToS / paywall / not worth)

---

## ✅ Already configured

| Service | Env var | Tier | Note |
|---|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | Paid (~$2 left) | `perbrinell@gmail.com` key. Use :free models only. |
| Supabase (local) | `SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY` | Self-hosted | Via Docker on :54421. No key from a SaaS. |
| Ollama | (none) | Local | `http://localhost:11434`. Models on disk. |
| Qdrant | (none) | Local | Docker on :6333. |
| GitHub PATs (4) | `GH_TOKEN_*` | Free tier | Per has 4. Watch for expiry. |

---

## 🟡 Sign up tomorrow (in priority order)

### High value for TANGLE entity research
1. **OpenCorporates** — https://api.opencorporates.com/users/sign_up
   - Use: structured company data (names, addresses, officers, filings) global
   - Free tier: 200 req/day, 5 req/sec
   - Env: `OPENCORPORATES_API_KEY`

2. **CourtListener** — https://www.courtlistener.com/help/api/rest/
   - Use: US federal + state case law (NOT relevant for Swedish, but good for benchmark)
   - Free tier: unlimited (just rate-limited)
   - Env: `COURTLISTENER_API_KEY` (optional — works without for low volume)

3. **TinyFish** — https://agent.tinyfish.ai (was mentioned earlier in your notes)
   - Use: agentic web search + extract (live web, no LLM needed for the agent)
   - Free for every account (no credits system)
   - Env: `TINYFISH_API_KEY`

4. **Google AI Studio (Gemini)** — https://aistudio.google.com/apikey
   - Use: 2nd-tier chat fallback, also vision via Gemini Flash
   - Free tier: 15 RPM, 1500 RPD; 2.0 Flash available
   - Env: `GEMINI_API_KEY`

### Medium value for SKATTEREVISION-REBOOT (your tax project)
5. **Riksdagen öppet data** — https://data.riksdagen.se/
   - Use: Swedish statutes, motions, voting records
   - **No key required** — public API
   - Endpoints: `https://data.riksdagen.se/`

6. **HFD RSS / öppna data** — https://www.domstol.se/
   - Use: Swedish tax precedents (HFD = Högsta förvaltningsdomstolen)
   - **No key, no clean API** — RSS feeds on domstol.se + web scraping
   - Bulk download via `wget` recursive (you've done this before)

### Nice to have (skip for now)
7. **Brave Search API** — https://brave.com/search/api/ (2k req/month free; better than Jina for search-only)
8. **Serper.dev** — https://serper.dev ($1 trial credit; Google Search results via API)
9. **Cohere trial** — https://dashboard.cohere.com (free trial credits for reranking)

---

## 🔵 No key needed (just configure endpoints)

| Service | Use | Endpoint / docs |
|---|---|---|
| **Wikidata SPARQL** | Entity enrichment (freebase replacement) | `https://query.wikidata.org/sparql` |
| **DBpedia** | Structured Wikipedia data | `https://dbpedia.org/sparql` |
| **OpenAlex** | Open academic paper search | `https://api.openalex.org/` |
| **GitHub REST** | Repo + code search (PAT optional, lowers rate) | `https://api.github.com/` |
| **Riksdagen** | Swedish law data | `https://data.riksdagen.se/` |

---

## ❌ Skipped (reasons)

- **Crunchbase / PitchBook** — paywalled, $$$$
- **Bloomberg / Refinitiv** — institutional pricing
- **LinkedIn scraping** — ToS violation
- **Westlaw / LexisNexis** — paywalled legal DBs (CourtListener + HFD is the free alternative)
- **Anthropic / OpenAI paid tiers** — over budget; DeepSeek/Qwen/Nemotron :free covers 80%

---

## 🔑 How to plug new keys into TANGLE

```bash
# 1. Add to .env (which is gitignored — never committed)
echo "OPENCORPORATES_API_KEY=..." >> /Users/perbrinell/Documents/DROPHELP/.env
echo "COURTLISTENER_API_KEY=..." >> /Users/perbrinell/Documents/DROPHELP/.env

# 2. Update free_gateway.py (or vector_store.py for embeddings) to read the new env var.
#    Pattern:
#        key = os.getenv("OPENCORPORATES_API_KEY", "")
#        if not key: return fallback_msg
#        # ... use httpx or supabase-py to call API ...

# 3. Add a custom agent to agent_orchestrator.py that uses the new connector
#    (or a scout source in TANGLE_SCOUT_SOURCE).

# 4. Add to .env.example with comment + link to sign-up page
# 5. Commit code change with feat: ... message
# 6. Restart TANGLE backend (lsof -ti:8000 | xargs kill -9; python main.py &)
```

---

## 🛡️ Security reminder

After signing up: **rotate the keys you pasted into chat history during this session** (the four OpenRouter keys + three GitHub PATs are sitting in cleartext at `~/.config/manicode/message-history.json`). If you sync `~/.config/` to cloud backup, they're already leaked. Best to regenerate the most sensitive ones (wawawee/leadagenticos GitHub PATs first).

---

## 📋 Tomorrow's checklist (TL;DR)

```
□ Sign up: OpenCorporates          → OPENCORPORATES_API_KEY
□ Sign up: CourtListener           → COURTLISTENER_API_KEY (optional)
□ Sign up: TinyFish                → TINYFISH_API_KEY
□ Sign up: Google AI Studio        → GEMINI_API_KEY (if you want a paid-tier safety net)
□ Rotate: leadagenticos GitHub PAT (was in chat history)
□ Rotate: wawawee GitHub PAT       (was in chat history)
□ Plug keys into .env
□ Run scripts/eval_gates.py to confirm nothing breaks
□ Pick ONE integration to build tomorrow (my pick: OpenCorporates)
```
