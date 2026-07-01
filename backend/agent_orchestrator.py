"""Pi-Inspired Agent Orchestration Core for TANGLE"""

import os
import re
import json
import uuid
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
import httpx

from free_gateway import FreeGateway
from parsing_engine import ParsingEngine
from vector_store import VectorStore
from wiki_vault import WikiVault, export_on_mission_enabled
from skill_router import SkillRouter
import guardrails
from phases import (
    MissionContext, MissionPhase, DEFAULT_PHASES,
    PlanningPhase, ResearchPhase, EvaluationPhase, SynthesisPhase, IngestionPhase,
)
import metrics as tangle_metrics

logger = logging.getLogger("tangle.orchestrator")

# ── Scout source selection ────────────────────────────────────
# jina       → Jina AI search only (default, no local resources)
# exa        → Exa AI-native search (20k free req/month)
# crawl4ai   → Jina search for URLs → Crawl4AI deep-crawls top 2-3
# exa-crawl  → Exa search for URLs → Crawl4AI deep-crawls top 2-3
# both       → Jina search + Crawl4AI crawl combined
SCOUT_SOURCE = os.getenv("TANGLE_SCOUT_SOURCE", "jina").strip().lower()
EXA_API_KEY = os.getenv("EXA_API_KEY", "")

CRAWL4AI_AVAILABLE = False
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    if SCOUT_SOURCE in ("crawl4ai", "both", "exa-crawl"):
        logger.warning(
            f"TANGLE_SCOUT_SOURCE={SCOUT_SOURCE} but crawl4ai not installed. "
            f"Falling back to jina. Install: pip install crawl4ai"
        )
        SCOUT_SOURCE = "jina"

AGENT_DEFS = {
    "planner": {
        "name": "Planner",
        "prompt": "You are the PLANNER agent. Your job is to decompose the assistance mission for '{entity}' into structured research subtasks. Identify gaps in our current information and list 2-3 specific queries that the Scout agent should search for."
    },
    "scout": {
        "name": "Scout",
        "prompt": "You are the SCOUT agent. Your job is to search the web and extract current external information, facts, and risks for the entity '{entity}'."
    },
    "librarian": {
        "name": "Librarian",
        "prompt": "You are the LIBRARIAN agent. Your job is to read and extract information from the internal wiki database using vector search queries related to '{entity}'."
    },
    "critic": {
        "name": "Critic",
        "prompt": "You are the CRITIC agent. Your job is to evaluate whether the gathered intelligence is sufficient and accurate. Provide constructive critique and output a success score between 0.0 and 1.0. You must return a JSON response containing 'score' (float) and 'critique' (string)."
    },
    "image_analyst": {
        "name": "Image Analyst",
        "prompt": "You are the IMAGE ANALYST agent specialized in extracting structured information from images (photos, scans, screenshots, charts, diagrams). Your job is to analyze the visual content for entity '{entity}' and produce a detailed, factual markdown description. Include any visible text, objects, people, layouts, colors, branding, and contextual cues. Flag anything ambiguous or low-confidence."
    },
    "synthesizer": {
        "name": "Synthesizer",
        "prompt": "You are the SYNTHESIZER agent. Your job is to merge all findings (web search results, wiki chunks, and agent insights) into a master report and format it as a radiating network structure of recommendations, risks, and facts."
    }
}

class AgentOrchestrator:
    # Agent definitions (prompts and metadata)
    AGENT_DEFS = AGENT_DEFS

    # Agent → preferred free model (tiered by role fit, context length, and reliability).
    # Order = fallback order within each tier. Top of list = best first choice.
    AGENT_MODELS = {
        # High-reasoning / planning / synthesis → best structured-output models
        "planner": [
            "openrouter/qwen/qwen3-coder:free",
            "openrouter/openai/gpt-oss-120b:free",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        ],
        "synthesizer": [
            "openrouter/qwen/qwen3-coder:free",
            "openrouter/openai/gpt-oss-120b:free",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
        ],
        # Scout (web search summarization) → solid all-rounder
        "scout": [
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
            "openrouter/openai/gpt-oss-120b:free",
        ],
        # Librarian (internal wiki recall) → strong long-context summarizer
        "librarian": [
            "openrouter/openai/gpt-oss-120b:free",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
        ],
        # Critic (JSON eval gate) → disciplined instruction follower
        "critic": [
            "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
            "openrouter/qwen/qwen3-coder:free",
            "openrouter/openai/gpt-oss-120b:free",
        ],
        # Image analyst → vision-capable
        "image_analyst": [
            "openrouter/nvidia/nemotron-nano-12b-v2-vl:free",
            "openrouter/google/gemma-4-31b-it:free",
        ],
        # Generic / unknown agent
        "default": [
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/openai/gpt-oss-120b:free",
            "openrouter/nousresearch/hermes-3-llama-3.1-405b:free",
            "openrouter/meta-llama/llama-3.2-3b-instruct:free",
        ],
    }

    def __init__(self, gateway: FreeGateway):
        self.gateway = gateway
        self.parser = ParsingEngine(gateway=gateway)
        self.parser.on_event(lambda ev: self._emit(ev))
        self.vector_store = VectorStore()
        self.wiki_vault = WikiVault()
        self.callbacks: List[Callable[[Dict], None]] = []
        self._missions: Dict[str, MissionContext] = {}  # concurrent mission tracking
        self._current_mission_id: Optional[str] = None  # threaded to gateway for cost tracking
        # Global fallback only; delegate() prefers agent-specific list above.
        # Override via TANGLE_DEFAULT_MODEL env var, e.g. "lmstudio/google/gemma-4-26b-a4b"
        self.default_model = os.getenv("TANGLE_DEFAULT_MODEL", "openrouter/meta-llama/llama-3.3-70b-instruct:free")
        # Phase pipeline (configurable via subclass or injection)
        self._phases: List[MissionPhase] = [phase(self) for phase in DEFAULT_PHASES]
        # Pending user decisions (blocking mission until resolved)
        self._pending_decisions: Dict[str, asyncio.Event] = {}
        self._decision_results: Dict[str, str] = {}
        # SkillRouter — embedding-based skill selection
        skills_dir = os.path.join(os.path.dirname(__file__), "skills")
        self.skill_router = SkillRouter(
            skill_dir=skills_dir,
            embed_fn=self._embed_for_skill,
            threshold=float(os.getenv("TANGLE_SKILL_THRESHOLD", "0.60")),
            top_k=int(os.getenv("TANGLE_SKILL_TOP_K", "5")),
        )

    async def _embed_for_skill(self, text: str) -> List[float]:
        """Wrapper to reuse vector_store embeddings for SkillRouter."""
        return await self.vector_store.get_embeddings(text)

    def _ctx(self) -> dict:
        """Build agent_context dict for gateway calls (carries mission_id)."""
        return {"mission_id": self._current_mission_id} if self._current_mission_id else {}

    def on_event(self, cb: Callable[[Dict], None]):
        self.callbacks.append(cb)

    def _emit(self, event: Dict[str, Any]):
        import time
        event["ts"] = time.time()
        for cb in self.callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    # ── Decision Points (Human-in-the-Loop) ───────────

    async def request_decision(self, mission_id: str, title: str, description: str, options: list[dict]) -> str:
        """Emit a decision point and wait for user choice.

        Each option: { id: str, title: str, summary: str, confidence: float, pros: list[str], cons: list[str] }
        Returns the chosen option_id, or the first option if user skips.
        """
        event = {
            "type": "DECISION_POINT",
            "payload": {
                "id": mission_id,
                "title": title,
                "description": description,
                "options": options,
            }
        }
        self._emit(event)

        # Wait for user decision (with timeout fallback to first option)
        ev = asyncio.Event()
        self._pending_decisions[mission_id] = ev
        try:
            await asyncio.wait_for(ev.wait(), timeout=300.0)  # 5 min timeout
        except asyncio.TimeoutError:
            logger.warning(f"Decision timeout for mission {mission_id}, using first option")
            self._decision_results[mission_id] = options[0]["id"]
        finally:
            self._pending_decisions.pop(mission_id, None)

        return self._decision_results.pop(mission_id, options[0]["id"])

    def resolve_decision(self, mission_id: str, option_id: str) -> bool:
        """Resolve a pending decision — called from API endpoint."""
        self._decision_results[mission_id] = option_id
        ev = self._pending_decisions.get(mission_id)
        if ev:
            ev.set()
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    # Core 6-Tool Surface (Pi Philosophy)
    # ─────────────────────────────────────────────────────────────

    async def ingest(self, filepath: str, entity_name: str) -> Dict[str, Any]:
        """Tool 1: Ingest file, parse, extract structure, and vectorize."""
        self._emit({"type": "tool_call", "agent_id": "orchestrator", "tool": "ingest", "args": {"filepath": filepath, "entity": entity_name}})
        try:
            parsed = await self.parser.parse_file(filepath, entity_name)
            await self.vector_store.add_wiki_entry(parsed, entity_name)
            self._emit({"type": "tool_result", "agent_id": "orchestrator", "tool": "ingest", "result": f"Ingested {parsed['filename']} successfully"})
            return parsed
        except Exception as e:
            err = f"Ingestion error: {e}"
            self._emit({"type": "tool_result", "agent_id": "orchestrator", "tool": "ingest", "result": err})
            return {"error": err}

    async def _crawl_urls(self, urls: List[str], agent_id: str, timeout_per_url: int = 20) -> str:
        """Deep-crawl a list of URLs with Crawl4AI. Returns combined Markdown.

        Each URL is crawled with a browser instance — heavy operation.
        Limit to 2-3 URLs per call to keep mission latency reasonable.
        """
        if not CRAWL4AI_AVAILABLE:
            return ""
        crawled: List[str] = []
        try:
            async with AsyncWebCrawler() as crawler:
                for i, url in enumerate(urls[:3]):
                    try:
                        self._emit({
                            "type": "tool_call",
                            "agent_id": agent_id,
                            "tool": "crawl4ai",
                            "args": {"url": url, "idx": i + 1},
                        })
                        result = await asyncio.wait_for(
                            crawler.arun(url=url, bypass_cache=True),
                            timeout=timeout_per_url,
                        )
                        md = (result.markdown or "").strip()
                        if md and len(md) > 50:
                            page = md[:1500]
                            if len(md) > 1500:
                                page += f"\n\n…truncated ({len(md) - 1500} more chars)"
                            crawled.append(f"## Crawled: {url}\n\n{page}")
                            self._emit({
                                "type": "tool_result",
                                "agent_id": agent_id,
                                "tool": "crawl4ai",
                                "result": f"{url}: {len(md)} chars Markdown",
                            })
                        else:
                            self._emit({
                                "type": "tool_result",
                                "agent_id": agent_id,
                                "tool": "crawl4ai",
                                "result": f"{url}: empty/invalid response",
                            })
                    except asyncio.TimeoutError:
                        logger.warning(f"Crawl4AI timeout for {url}")
                    except Exception as e:
                        logger.warning(f"Crawl4AI failed for {url}: {e}")
        except Exception as e:
            logger.warning(f"Crawl4AI crawler init failed: {e}")
        return "\n\n".join(crawled) if crawled else ""

    @staticmethod
    def _extract_urls_from_markdown(md: str) -> List[str]:
        """Pull http/https URLs from search response Markdown.

        Used for Jina search results which embed links as inline URLs.
        Exa returns structured JSON so doesn't need regex extraction.
        """
        found = re.findall(r'https?://[^\s)>"\x27]+', md)
        seen: set = set()
        unique: List[str] = []
        for u in found:
            u = u.rstrip(".!?,;:")
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique

    async def _search_exa(self, query: str, agent_id: str, num_results: int = 5) -> tuple[str, List[str]]:
        """Search via Exa API (AI-native search, 20k free req/month).

        Returns (formatted_markdown, extracted_urls).
        Exa returns structured JSON with title, url, text, score per result.
        """
        if not EXA_API_KEY:
            logger.warning("Exa search requested but EXA_API_KEY not set")
            return "", []
        try:
            self._emit({
                "type": "tool_call",
                "agent_id": agent_id,
                "tool": "exa_search",
                "args": {"query": query, "num_results": num_results},
            })
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    "https://api.exa.ai/search",
                    headers={
                        "x-api-key": EXA_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={"query": query, "type": "auto", "numResults": num_results},
                )
                if resp.status_code != 200:
                    logger.warning(f"Exa API returned {resp.status_code}: {resp.text[:200]}")
                    return "", []
                data = resp.json()
                results = data.get("results", [])
                if not results:
                    return "", []

                # Assemble Markdown from structured results
                parts: List[str] = []
                urls: List[str] = []
                for i, r in enumerate(results):
                    title = r.get("title", "Untitled")
                    url = r.get("url", "")
                    text = (r.get("text") or "").strip()
                    score = r.get("score", 0)
                    published = r.get("publishedDate", "")
                    if url:
                        urls.append(url)
                    header = f"## [{i+1}] {title}"
                    meta_parts = []
                    if published:
                        meta_parts.append(published)
                    if score:
                        meta_parts.append(f"score: {score:.2f}")
                    meta = f"{url} ({', '.join(meta_parts)})" if meta_parts else url
                    # Cap text per result at 600 chars (5 results × 600 ≈ 3000 total)
                    body = text[:600] if text else "[no content]"
                    if text and len(text) > 600:
                        body += f"\n…truncated ({len(text) - 600} more chars)"
                    parts.append(f"{header}\n{meta}\n\n{body}")

                content = "\n\n".join(parts)
                self._emit({
                    "type": "tool_result",
                    "agent_id": agent_id,
                    "tool": "exa_search",
                    "result": f"Exa: {len(results)} results, {len(urls)} URLs",
                })
                return content, urls
        except Exception as e:
            logger.warning(f"Exa search failed: {e}")
            return "", []

    async def _search_jina(self, query: str, agent_id: str) -> tuple[str, List[str]]:
        """Search via Jina AI (s.jina.ai). Returns (formatted_markdown, extracted_urls).

        Free for basic usage — 20 req/min without API key, 500 with.
        """
        from urllib.parse import quote
        jina_token = os.getenv("JINA_API_KEY", "")
        jina_headers: Dict[str, str] = {
            "Accept": "text/plain",
            "User-Agent": "TANGLE/2.0",
        }
        if jina_token:
            jina_headers["Authorization"] = f"Bearer {jina_token}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"https://s.jina.ai/?q={quote(query)}",
                    headers=jina_headers,
                )
                if resp.status_code == 200:
                    content = resp.text.strip()
                    if content and len(content) > 20:
                        urls = self._extract_urls_from_markdown(content)
                        self._emit({
                            "type": "tool_result",
                            "agent_id": agent_id,
                            "tool": "jina_search",
                            "result": f"Jina: {len(content)} chars, {len(urls)} URLs",
                        })
                        return content, urls
        except Exception as e:
            logger.warning(f"Jina AI search failed: {e}")
        return "", []

    async def _search_duckduckgo(self, query: str, agent_id: str) -> tuple[str, List[str]]:
        """Search via DuckDuckGo (free, no API key needed). Returns (formatted_markdown, urls)."""
        try:
            from ddgs import DDGS
            results = []
            urls = []
            for r in DDGS().text(query, max_results=5):
                title = r.get("title", "")
                body = r.get("body", "")
                url = r.get("href", "")
                if title and body:
                    results.append(f"### {title}\n{body}\n")
                    if url:
                        urls.append(url)
            if results:
                content = "\n".join(results)
                self._emit({
                    "type": "tool_result",
                    "agent_id": agent_id,
                    "tool": "duckduckgo_search",
                    "result": f"DuckDuckGo: {len(content)} chars, {len(urls)} URLs",
                })
                return content, urls
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
        return "", []

    async def search(self, query: str, agent_id: str = "scout") -> str:
        """Tool 2: Web search via Jina, Exa, or Crawl4AI depending on SCOUT_SOURCE.

        Sources (TANGLE_SCOUT_SOURCE env var):
          jina       → Jina AI search (default, needs JINA_API_KEY)
          exa        → Exa AI-native search (20k free req/month, needs EXA_API_KEY)
          crawl4ai   → Jina + Crawl4AI deep-crawl
          exa-crawl  → Exa + Crawl4AI deep-crawl
          both       → Jina + Crawl4AI deep-crawl

        Falls back to DuckDuckGo (free, no key) if Jina fails.
        Falls back to OpenRouter LLM search if all search providers are unreachable.
        """
        self._emit({"type": "tool_call", "agent_id": agent_id, "tool": "search", "args": {"query": query}})
        use_crawl = SCOUT_SOURCE in ("crawl4ai", "both", "exa-crawl") and CRAWL4AI_AVAILABLE
        use_exa = SCOUT_SOURCE in ("exa", "exa-crawl") and bool(EXA_API_KEY)
        if SCOUT_SOURCE in ("exa", "exa-crawl") and not EXA_API_KEY:
            logger.warning(
                f"TANGLE_SCOUT_SOURCE={SCOUT_SOURCE} but EXA_API_KEY not set. "
                f"Falling back to jina."
            )

        # ── 1. Primary Search ───────────────────────────────
        if use_exa:
            primary_content, urls = await self._search_exa(query, agent_id)
            source_label = "Exa"
        else:
            primary_content, urls = await self._search_jina(query, agent_id)
            source_label = "Jina AI"
            # Fallback to DuckDuckGo if Jina returns nothing
            if not primary_content:
                logger.info("Jina returned empty, trying DuckDuckGo fallback")
                primary_content, urls = await self._search_duckduckgo(query, agent_id)
                source_label = "DuckDuckGo"

        # ── 2. Deep Crawl (shared logic) ────────────────────
        crawl_content = ""
        if use_crawl and primary_content and urls:
            logger.info(f"Crawl4AI mode: deep-crawling top {min(3, len(urls))} URLs from {source_label} results")
            crawl_content = await self._crawl_urls(urls, agent_id)

        # ── 3. Assemble result (shared logic) ───────────────
        if primary_content:
            total_chars = len(primary_content) + len(crawl_content)
            label = f"{source_label} + Crawl4AI" if crawl_content else source_label

            if crawl_content:
                primary_portion = primary_content[:2000]
                if len(primary_content) > 2000:
                    primary_portion += f"\n\n…truncated ({len(primary_content) - 2000} more chars in search results)"
                body = f"Search results for '{query}':\n\n{primary_portion}\n\n─── Deep-crawled pages ───\n\n{crawl_content}"
            else:
                primary_portion = primary_content[:3000]
                if len(primary_content) > 3000:
                    primary_portion += f"\n\n…truncated ({len(primary_content) - 3000} more chars)"
                body = primary_portion

            self._emit({"type": "tool_result", "agent_id": agent_id, "tool": "search", "result": f"{label}: {total_chars} chars"})
            return f"{label} Search results for '{query}':\n\n{body}"

        # ── Fallback: LLM search via OpenRouter ──────────────
        try:
            messages = [
                {"role": "system", "content": (
                    "You are a web search helper. If you genuinely know facts about the query "
                    "from your training data, share them concisely. If you are uncertain, say "
                    "'Web search unavailable — no real-time data.' Do NOT fabricate information."
                )},
                {"role": "user", "content": f"Search query: {query}"},
            ]
            resp = await self.gateway.chat(self.default_model, messages, agent_context=self._ctx())
            res = resp.get("content", "No information found.")
            self._emit({"type": "tool_result", "agent_id": agent_id, "tool": "search", "result": res[:300] + "..."})
            return f"LLM Knowledge (web search unavailable) for '{query}':\n{res}"
        except Exception as e:
            return f"Search service temporarily offline: {e}"

    async def query_memory(self, query: str, entity_name: str, agent_id: str = "librarian") -> str:
        """Tool 3: Search internal vectorized wiki memory."""
        self._emit({"type": "tool_call", "agent_id": agent_id, "tool": "query_memory", "args": {"query": query, "entity": entity_name}})
        try:
            results = await self.vector_store.search_wiki(query, entity_name)
            if not results:
                res = "No matching document entries found."
            else:
                res = "\n\n".join([f"--- From: {r['filename']} ---\n{r['raw_content'][:800]}" for r in results])
            self._emit({"type": "tool_result", "agent_id": agent_id, "tool": "query_memory", "result": f"Found {len(results)} matches"})
            return res
        except Exception as e:
            err = f"Memory retrieval error: {e}"
            self._emit({"type": "tool_result", "agent_id": agent_id, "tool": "query_memory", "result": err})
            return err

    async def evaluate(self, output: str, criteria: str, threshold: float = 0.7) -> Dict[str, Any]:
        """Tool 4: Evaluation gate check using Critic agent.

        Returns dict with: passed (bool), score (float 0-1), critique (str), verified (bool).
        - verified=True: critic ran successfully
        - verified=False: critic errored; report should be marked [UNVERIFIED] downstream
        """
        self._emit({"type": "tool_call", "agent_id": "critic", "tool": "evaluate", "args": {"criteria": criteria}})

        prompt = (
            f"{AGENT_DEFS['critic']['prompt']}\n\n"
            f"Evaluation Criteria:\n{criteria}\n\n"
            f"Output to evaluate:\n{output}\n\n"
            f"Respond with JSON format only, including 'score' (0.0 to 1.0) and 'critique' (string)."
        )

        messages = [
            {"role": "system", "content": "You are a JSON assistant. Always respond with raw JSON."},
            {"role": "user", "content": prompt}
        ]

        try:
            resp = await self.gateway.chat(self.default_model, messages, agent_context=self._ctx())
            content = resp.get("content", "").strip()
            # Clean markdown codeblocks if model wraps it
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            data = json.loads(content)
            score = float(data.get("score", 0.0))
            critique = data.get("critique", "No critique provided.")

            passed = score >= threshold
            verified = True
            self._emit({"type": "tool_result", "agent_id": "critic", "tool": "evaluate", "result": f"Passed: {passed} (Score: {score})"})
            return {"passed": passed, "score": score, "critique": critique, "verified": verified}
        except Exception as e:
            # FAIL OPEN — do NOT silently pass. Mark as unverified so downstream
            # can render [UNVERIFIED] badge in UI rather than claim quality we
            # don't have.
            logger.error(f"Critic evaluation failed: {e}")
            return {
                "passed": False,
                "score": 0.5,
                "critique": f"VERIFICATION FAILED: {type(e).__name__}: {e}. Report marked [UNVERIFIED].",
                "verified": False,
            }

    def _model_for_agent(self, agent_id: str) -> str:
        """Pick the best model for a given agent.

        When default_model is local (lmstudio/), agents use it directly.
        When default_model is remote (openrouter/), use the agent-specific
        chain for role-optimized model selection.
        """
        if self.default_model.startswith("lmstudio/"):
            return self.default_model
        chain = self.AGENT_MODELS.get(agent_id, self.AGENT_MODELS["default"])
        for candidate in chain:
            return candidate
        return self.default_model

    async def delegate(self, task: str, agent_id: str, entity_name: str, skill_context: str = "") -> str:
        """Tool 5: Delegate subtask to a specialized agent.

        Model selection is role-aware: planner/synthesizer lean toward structured-output
        coders, critic toward instruction-followers, scout/librarian toward generalists,
        image_analyst toward vision. Each role has an ordered fallback chain in
        `AGENT_MODELS`.

        Args:
            skill_context: Injected domain knowledge from SkillRouter (prepended to system prompt).
        """
        self._emit({"type": "sub_delegate", "from": "orchestrator", "to": agent_id, "task": task})
        self._emit({"type": "agent_start", "agent_id": agent_id, "task": task})

        agent_def = AGENT_DEFS.get(agent_id, {"name": "Assistant", "prompt": "You are a helpful assistant."})
        base_prompt = agent_def["prompt"].format(entity=entity_name)
        system_prompt = f"{skill_context}\n\n{base_prompt}" if skill_context else base_prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        try:
            self._emit({"type": "agent_think", "agent_id": agent_id, "turn": 1})

            # Pre-fetch search/memory context for agents that use those tools
            if agent_id == "scout":
                search_results = await self.search(task, agent_id=agent_id)
                messages.append({
                    "role": "user",
                    "content": (
                        "Here are the search results:\n"
                        f"{search_results}\n\n"
                        "Summarize the key facts, risks, and opportunities."
                    ),
                })
            elif agent_id == "librarian":
                mem_results = await self.query_memory(task, entity_name, agent_id=agent_id)
                messages.append({
                    "role": "user",
                    "content": (
                        "Here is the wiki document content:\n"
                        f"{mem_results}\n\n"
                        "Summarize the internal file knowledge."
                    ),
                })

            model = self._model_for_agent(agent_id)
            resp = await self.gateway.chat(model, messages, agent_context=self._ctx())
            res = resp.get("content", "Error generating response.")

            self._emit({"type": "agent_complete", "agent_id": agent_id, "result": res[:500] + "..."})
            return res
        except Exception as e:
            err = f"Agent delegation error: {e}"
            self._emit({"type": "agent_error", "agent_id": agent_id, "error": err})
            return err

    async def synthesize(self, findings: List[str], entity_name: str, critic_score: Optional[float] = None, verified: bool = False, skill_context: str = "") -> Dict[str, str]:
        """Tool 6: Synthesize all agent inputs into BOTH a human report AND a re-ingestable wiki entry.

        Returns dict with:
            report_markdown     — human-readable report with ```json wiki-nodes``` block at end (frontend reads this)
            wiki_entry_markdown — wiki-spec compliant markdown (Entity / Source / Extracted / Confidence / Chunk ID / Tags)
            wiki_entry_chunk_id — deterministic UUID for the synthesized entry (so orchestrator can persist it)

        The two outputs are produced in a single LLM call using explicit delimiters:
            ===TANGLE_REPORT_START=== ... ===TANGLE_REPORT_END===
            ===TANGLE_WIKI_START===   ... ===TANGLE_WIKI_END===

        If parsing fails, the full response is used for both fields (degraded but non-fatal).
        """
        self._emit({"type": "tool_call", "agent_id": "synthesizer", "tool": "synthesize", "args": {"entity": entity_name}})

        # Deterministic metadata — assigned in Python, not by the LLM
        chunk_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        source_filename = f"tangle-synthesis-{entity_name.lower().replace(' ', '-')[:40]}-{timestamp[:10]}.md"
        confidence = self._confidence_from_critic(critic_score, verified)

        compiled_findings = "\n\n".join([f"### Finding {i+1}:\n{f}" for i, f in enumerate(findings)])

        prompt = (
            f"You are the SYNTHESIZER agent for TANGLE.\n\n"
            f"Your job: produce TWO clearly delimited outputs from the gathered findings for entity '{entity_name}'.\n\n"
            f"═══════════════════════════════════════\n"
            f"INPUT FINDINGS\n"
            f"═══════════════════════════════════════\n"
            f"{compiled_findings}\n\n"
            f"═══════════════════════════════════════\n"
            f"OUTPUT 1: REPORT_MARKDOWN (human-readable, shown in UI side panel)\n"
            f"═══════════════════════════════════════\n"
            f"Produce a comprehensive, structured markdown report with:\n"
            f"- Executive summary (2-3 sentences)\n"
            f"- Key findings (organized by theme)\n"
            f"- Recommended actions (concrete, prioritized)\n"
            f"- Risks and gaps\n"
            f"End the report with a ```json``` code block listing the Wiki Nodes that should appear "
            f"on the radiating graph. Frontend reads this block to render the network.\n\n"
            f"Example wiki-nodes JSON:\n"
            f"```json\n"
            f'{{"nodes": [\n'
            f'  {{"id": "node_1", "label": "Diet recommendations", "type": "info", "details": "High protein food"}},\n'
            f'  {{"id": "node_2", "label": "Veterinary checkup", "type": "warning", "details": "Schedule dental review"}}\n'
            f"]}}\n"
            f"```\n\n"
            f"═══════════════════════════════════════\n"
            f"OUTPUT 2: WIKI_ENTRY_BODY (re-ingestable, follows TANGLE wiki spec)\n"
            f"═══════════════════════════════════════\n"
            f"Produce the BODY of a wiki entry. Metadata headers (Entity / Source / Extracted / "
            f"Confidence / Chunk ID) will be injected automatically — you write ONLY the body. "
            f"This must be vector-search-friendly: dense, factual, no marketing language.\n\n"
            f"Required body structure:\n"
            f"[Opening paragraph: 2-3 sentence summary of the synthesized understanding of '{entity_name}', suitable for vector search]\n\n"
            f"## Findings\n"
            f"[For each major finding: a subsection with a bolded headline + 1-2 paragraphs of detail. "
            f"Cite source inline as (Scout), (Librarian), (Uploaded file), (Retry).]\n\n"
            f"## Recommended Actions\n"
            f"[Numbered list of concrete next steps]\n\n"
            f"## Open Questions\n"
            f"[Things that need more research or human input]\n\n"
            f"### Tags\n"
            f"[5-10 inline tags from: #health #finance #legal #contact #risk #opportunity #threat #context "
            f"#research #urgent — or invent new ones if needed. One line, space-separated.]\n\n"
            f"═══════════════════════════════════════\n"
            f"DELIMITERS — use these EXACT markers (no extra whitespace before/after):\n"
            f"═══════════════════════════════════════\n"
            f"===TANGLE_REPORT_START===\n"
            f"[your human-readable report, ending with the ```json wiki-nodes block```]\n"
            f"===TANGLE_REPORT_END===\n\n"
            f"===TANGLE_WIKI_START===\n"
            f"[your wiki-spec body content per OUTPUT 2 structure]\n"
            f"===TANGLE_WIKI_END===\n"
        )

        synth_prompt = AGENT_DEFS["synthesizer"]["prompt"].format(entity=entity_name)
        if skill_context:
            synth_prompt = f"{skill_context}\n\n{synth_prompt}"
        messages = [
            {"role": "system", "content": synth_prompt},
            {"role": "user", "content": prompt}
        ]

        try:
            resp = await self.gateway.chat(self.default_model, messages, agent_context=self._ctx())
            raw = resp.get("content", "")
            report_md, wiki_body = self._split_synth_response(raw)

            # If LLM didn't honor delimiters, degrade gracefully
            if not report_md:
                report_md = raw
                logger.warning("Synthesizer response missing REPORT delimiters — using raw content for report_markdown")
            if not wiki_body:
                wiki_body = raw
                logger.warning("Synthesizer response missing WIKI delimiters — using raw content for wiki_entry body")

            wiki_entry_markdown = self._assemble_wiki_entry(
                entity_name=entity_name,
                source_filename=source_filename,
                timestamp=timestamp,
                confidence=confidence,
                chunk_id=chunk_id,
                body=wiki_body,
                tags=self._extract_tags_from_body(wiki_body),
            )

            self._emit({
                "type": "tool_result",
                "agent_id": "synthesizer",
                "tool": "synthesize",
                "result": f"Dual output: report ({len(report_md)} chars) + wiki entry (chunk {chunk_id[:8]}…)"
            })

            return {
                "report_markdown": report_md,
                "wiki_entry_markdown": wiki_entry_markdown,
                "wiki_entry_chunk_id": chunk_id,
            }
        except Exception as e:
            err = f"Synthesis failed: {e}"
            logger.error(err)
            self._emit({"type": "tool_result", "agent_id": "synthesizer", "tool": "synthesize", "result": err})
            # Return minimal stub so run_mission doesn't blow up
            return {
                "report_markdown": f"# Synthesis failed\n\n{err}",
                "wiki_entry_markdown": "",
                "wiki_entry_chunk_id": chunk_id,
            }

    @staticmethod
    def _split_synth_response(raw: str) -> tuple[str, str]:
        """Parse the dual-delimited synth response. Returns (report, wiki_body). Either may be empty."""
        if not raw:
            return "", ""
        # Greedy match between START and END markers; tolerate any whitespace inside the tag
        report_match = re.search(
            r"===TANGLE_REPORT_START===\s*(.*?)\s*===TANGLE_REPORT_END===",
            raw,
            flags=re.DOTALL,
        )
        wiki_match = re.search(
            r"===TANGLE_WIKI_START===\s*(.*?)\s*===TANGLE_WIKI_END===",
            raw,
            flags=re.DOTALL,
        )
        return (
            report_match.group(1).strip() if report_match else "",
            wiki_match.group(1).strip() if wiki_match else "",
        )

    @staticmethod
    def _assemble_wiki_entry(
        entity_name: str,
        source_filename: str,
        timestamp: str,
        confidence: float,
        chunk_id: str,
        body: str,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Wrap the LLM-produced wiki body with deterministic metadata headers per the TANGLE wiki spec.

        `tags` is the list of tag tokens (without the leading #). When empty/None,
        the synthesized entry is tagged '#synthesized' so vault consumers can
        distinguish LLM-generated from user-uploaded chunks. Real tags from the
        synth output override the fallback.
        """
        if not tags:
            tags = ["synthesized"]
        tag_line = " ".join(f"#{t}" for t in tags)
        return (
            f"# Entity: {entity_name}\n"
            f"## Source: {source_filename}\n"
            f"### Extracted: {timestamp}\n"
            f"### Confidence: {confidence:.2f}\n"
            f"### Chunk ID: {chunk_id}\n\n"
            f"{body.rstrip()}\n\n"
            f"### Related Chunks\n"
            f"- [[source-file:{source_filename}]]\n\n"
            f"### Tags\n"
            f"- {tag_line}\n"
        )

    @staticmethod
    def _extract_tags_from_body(body: str) -> List[str]:
        """Extract #tags from the synthesized wiki body. Same regex shape as
        parsing_engine so the two stay consistent."""
        if not body:
            return []
        # Match hashtags at word boundaries (avoid C#, F#, etc.)
        found = re.findall(r"(?:^|\s)#([a-z0-9][a-z0-9_-]{1,30})", body.lower())
        seen: set = set()
        unique: List[str] = []
        for t in found:
            if t not in seen:
                seen.add(t)
                unique.append(t)
            if len(unique) >= 8:
                break
        return unique

    @staticmethod
    def _confidence_from_critic(critic_score: Optional[float], verified: bool) -> float:
        """Map critic outcome to a wiki-entry confidence score.

        - critic verified + score >= 0.7 → use critic score (high trust)
        - critic verified + score < 0.7  → 0.5 (gate failed but content exists)
        - critic not verified            → 0.5 (explicitly unverified, lower trust)
        """
        if critic_score is None or not verified:
            return 0.5
        if critic_score >= 0.7:
            return float(critic_score)
        return 0.5

    # ─────────────────────────────────────────────────────────────
    # Main Orchestrator Mission Control Loop
    # ─────────────────────────────────────────────────────────────

    async def run_mission(self, entity_name: str, uploaded_filepath: Optional[str] = None) -> Dict[str, Any]:
        """Runs the complete assistance research mission from start to finish.

        Uses the phase pipeline for modularity and concurrent mission support.
        Pre-guardrails validate entity name, objective, and file paths before any cost.
        """
        mission_id = str(uuid.uuid4())
        self._current_mission_id = mission_id

        # Pre-guardrails: validate inputs before any cost
        pre_warnings = guardrails.apply_pre_guardrail(
            entity_name=entity_name,
            filepath=uploaded_filepath or "",
        )
        for w in pre_warnings:
            logger.warning(f"Pre-guardrail warning: {w}")

        # Sanitize entity name
        try:
            entity_name = guardrails.sanitize_entity_name(entity_name)
        except ValueError as e:
            return {
                "mission_id": mission_id,
                "entity_name": entity_name,
                "error": f"Invalid entity name: {e}",
                "verified": False,
            }

        # Initialize mission context
        ctx = MissionContext(
            mission_id=mission_id,
            entity_name=entity_name,
            uploaded_filepath=uploaded_filepath,
        )

        # Track mission for concurrent execution
        self._missions[mission_id] = ctx

        # Track metrics
        tangle_metrics.increment_active_missions()
        mission_start = time.time()

        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": f"Starting help mission for {entity_name}"})
        self._emit({"type": "agent_start", "agent_id": "maestro", "task": f"Analyze entity: {entity_name}"})

        try:
            # Step 1: Ingest file if provided (inline, not a phase)
            if uploaded_filepath:
                ctx.wiki_entry = await self.ingest(uploaded_filepath, entity_name)

            # Step 2: Skill selection (embedding match, no LLM call)
            self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Selecting relevant domain skills"})
            selected = await self.skill_router.select(entity_name, getattr(ctx, '_objective', ''))
            ctx.selected_skills = selected
            ctx.skill_context = self.skill_router.build_system_prompt(selected)
            if selected:
                skill_names = [f"{s[0]}({s[1]:.2f})" for s in selected]
                logger.info(f"Skills selected for '{entity_name}': {skill_names}")
                self._emit({"type": "skill_selection", "agent_id": "maestro", "skills": skill_names})

            # Execute phase pipeline
            for phase in self._phases:
                ctx = await phase.execute(ctx)

            # Record success metrics
            mission_duration = time.time() - mission_start
            tangle_metrics.record_mission_latency(mission_duration, status="success")

            return {
                "mission_id": ctx.mission_id,
                "entity_name": ctx.entity_name,
                # Backwards compat: frontend reads `data.report` and parses the wiki-nodes JSON block
                "report": ctx.report_markdown,
                # New: explicit dual-output fields
                "report_markdown": ctx.report_markdown,
                "wiki_entry_markdown": ctx.wiki_entry_markdown,
                "wiki_entry_chunk_id": ctx.wiki_entry_chunk_id,
                # Source-of-truth fields
                "wiki_entry": ctx.wiki_entry,
                "verified": ctx.evaluation.get("verified", False),
                "critic_score": ctx.evaluation.get("score"),
                "critic_critique": ctx.evaluation.get("critique"),
                "usage": ctx.usage,
                "wiki_export": ctx.wiki_export_summary,
                "contradiction_result": ctx.contradiction_result,
            }
        except Exception as e:
            # Record failure metrics
            mission_duration = time.time() - mission_start
            tangle_metrics.record_mission_latency(mission_duration, status="failed")
            raise
        finally:
            # Always clean up mission tracking
            self._missions.pop(mission_id, None)
            self._current_mission_id = None
            tangle_metrics.decrement_active_missions()

    async def execute(self, agent_id: str, task: str, max_turns: int = 6) -> dict:
        """Route execute to delegate for backwards compatibility with CLI/Chat panel"""
        res = await self.delegate(task, agent_id, "Target Entity")
        return {"agent_id": agent_id, "result": res, "turns": 1}

    async def workflow(self, tasks: list[dict]) -> dict:
        """Route workflow to sequential execution for backwards compatibility"""
        results = {}
        for t in tasks:
            aid = t["agent_id"]
            task_desc = t["task"]
            r = await self.execute(aid, task_desc)
            results[aid] = r
        return {"results": results}

    def stop(self):
        """Stop all running missions."""
        self._missions.clear()
        self._current_mission_id = None

    @property
    def _running(self) -> bool:
        """Check if any missions are running (for backward compatibility)."""
        return len(self._missions) > 0

    def get_active_missions(self) -> List[str]:
        """Return list of active mission IDs."""
        return list(self._missions.keys())
