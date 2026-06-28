"""Pi-Inspired Agent Orchestration Core for TANGLE"""

import os
import re
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
import httpx

from free_gateway import FreeGateway
from parsing_engine import ParsingEngine
from vector_store import VectorStore
from wiki_vault import WikiVault, export_on_mission_enabled

logger = logging.getLogger("tangle.orchestrator")

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
    "synthesizer": {
        "name": "Synthesizer",
        "prompt": "You are the SYNTHESIZER agent. Your job is to merge all findings (web search results, wiki chunks, and agent insights) into a master report and format it as a radiating network structure of recommendations, risks, and facts."
    }
}

class AgentOrchestrator:
    def __init__(self, gateway: FreeGateway):
        self.gateway = gateway
        self.parser = ParsingEngine(gateway=gateway)
        self.vector_store = VectorStore()
        self.wiki_vault = WikiVault()
        self.callbacks: List[Callable[[Dict], None]] = []
        self._running = False
        self._current_mission_id: Optional[str] = None  # threaded to gateway for cost tracking
        self.default_model = "openrouter/meta-llama/llama-3.3-70b-instruct:free"

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

    async def search(self, query: str, agent_id: str = "scout") -> str:
        """Tool 2: Search the web via DuckDuckGo HTML parsing or fallback to LLM knowledge if throttled."""
        self._emit({"type": "tool_call", "agent_id": agent_id, "tool": "search", "args": {"query": query}})
        
        # DuckDuckGo HTML Scraper fallback (API key free)
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=10) as client:
                resp = await client.get(f"https://html.duckduckgo.com/html/?q={httpx.URLEscaper().quote(query)}")
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "html.parser")
                    links = soup.find_all("a", class_="result__snippet")
                    snippets = [l.get_text().strip() for l in links[:5]]
                    if snippets:
                        res = "\n- ".join(snippets)
                        self._emit({"type": "tool_result", "agent_id": agent_id, "tool": "search", "result": res[:300] + "..."})
                        return f"Web Search results for '{query}':\n- " + res
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}. Falling back to internal LLM search.")

        # Fallback Search via OpenRouter
        try:
            messages = [
                {"role": "system", "content": "You are a web search helper. Simulate a search and return factual background information on the query."},
                {"role": "user", "content": f"Search query: {query}"}
            ]
            resp = await self.gateway.chat(self.default_model, messages, agent_context=self._ctx())
            res = resp.get("content", "No information found.")
            self._emit({"type": "tool_result", "agent_id": agent_id, "tool": "search", "result": res[:300] + "..."})
            return f"Mock Web Search results for '{query}':\n{res}"
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

    async def delegate(self, task: str, agent_id: str, entity_name: str) -> str:
        """Tool 5: Delegate subtask to a specialized agent."""
        self._emit({"type": "sub_delegate", "from": "orchestrator", "to": agent_id, "task": task})
        self._emit({"type": "agent_start", "agent_id": agent_id, "task": task})
        
        agent_def = AGENT_DEFS.get(agent_id, {"name": "Assistant", "prompt": "You are a helpful assistant."})
        system_prompt = agent_def["prompt"].format(entity=entity_name)
        
        # Determine appropriate tools based on agent
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        
        try:
            # Let the agent think
            self._emit({"type": "agent_think", "agent_id": agent_id, "turn": 1})
            
            # Simple agent execution loops: Scout searches, Librarian queries memory
            if agent_id == "scout":
                # First run search
                search_results = await self.search(task, agent_id=agent_id)
                messages.append({"role": "user", "content": f"Here are the search results:\n{search_results}\n\nSummarize the key facts, risks, and opportunities."})
            elif agent_id == "librarian":
                # Query internal documents
                mem_results = await self.query_memory(task, entity_name, agent_id=agent_id)
                messages.append({"role": "user", "content": f"Here is the wiki document content:\n{mem_results}\n\nSummarize the internal file knowledge."})
            
            resp = await self.gateway.chat(self.default_model, messages, agent_context=self._ctx())
            res = resp.get("content", "Error generating response.")
            
            self._emit({"type": "agent_complete", "agent_id": agent_id, "result": res[:500] + "..."})
            return res
        except Exception as e:
            err = f"Agent delegation error: {e}"
            self._emit({"type": "agent_error", "agent_id": agent_id, "error": err})
            return err

    async def synthesize(self, findings: List[str], entity_name: str, critic_score: Optional[float] = None, verified: bool = False) -> Dict[str, str]:
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

        messages = [
            {"role": "system", "content": AGENT_DEFS["synthesizer"]["prompt"].format(entity=entity_name)},
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
        """Runs the complete assistance research mission from start to finish"""
        self._running = True
        mission_id = str(uuid.uuid4())
        self._current_mission_id = mission_id  # threaded to gateway for cost tracking

        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": f"Starting help mission for {entity_name}"})
        self._emit({"type": "agent_start", "agent_id": "maestro", "task": f"Analyze entity: {entity_name}"})

        # Step 1: Ingest file if provided
        wiki_entry = None
        if uploaded_filepath:
            wiki_entry = await self.ingest(uploaded_filepath, entity_name)

        # Step 2: Planning Phase
        self._emit({"type": "agent_think", "agent_id": "planner", "turn": 1})
        plan_prompt = f"Develop a plan to research ways to help '{entity_name}'."
        if wiki_entry:
            plan_prompt += f" We have ingested files containing: {wiki_entry['raw_content'][:500]}"

        messages_plan = [
            {"role": "system", "content": AGENT_DEFS["planner"]["prompt"].format(entity=entity_name)},
            {"role": "user", "content": plan_prompt}
        ]

        plan_resp = await self.gateway.chat(self.default_model, messages_plan, agent_context=self._ctx())
        plan = plan_resp.get("content", "Research the entity.")
        self._emit({"type": "agent_complete", "agent_id": "planner", "result": plan[:400] + "..."})

        # Step 3: Dispatch Scout and Librarian in parallel
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Dispatching Research Agents"})

        scout_task = self.delegate(f"Search for external background, vulnerabilities, and solutions for {entity_name}.", "scout", entity_name)

        if wiki_entry:
            lib_task = self.delegate(f"Extract all relevant help insights and details for {entity_name} from the uploaded documents.", "librarian", entity_name)
            findings = await asyncio.gather(scout_task, lib_task)
        else:
            scout_result = await scout_task
            findings = [scout_result]

        # Step 4: Critique Phase (Evaluation Gate Loop)
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Evaluating gathered facts"})

        combined_text = "\n\n".join(findings)
        evaluation = await self.evaluate(
            combined_text,
            f"Does this content explain the situation of '{entity_name}' and provide concrete ways to help?"
        )

        # If low score, run scout again with refined queries (Phase 0 simplified: single retry loop)
        if not evaluation["passed"]:
            logger.info("Evaluation gate failed. Redo-ing scout query with critic feedback.")
            self._emit({"type": "workflow_step", "agent_id": "maestro", "task": f"Gate failed. Retrying: {evaluation['critique'][:100]}"})
            retry_findings = await self.delegate(
                f"Perform deeper research based on this critique: {evaluation['critique']}",
                "scout",
                entity_name
            )
            findings.append(retry_findings)

        # Step 5: Synthesize final output (dual output: report_markdown + wiki_entry_markdown)
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Synthesizing master report"})
        synth_result = await self.synthesize(
            findings,
            entity_name,
            critic_score=evaluation.get("score"),
            verified=evaluation.get("verified", False),
        )
        final_report = synth_result["report_markdown"]
        wiki_entry_markdown = synth_result["wiki_entry_markdown"]
        wiki_chunk_id = synth_result["wiki_entry_chunk_id"]

        self.vector_store.save_mission(mission_id, entity_name, final_report)
        self._emit({"type": "agent_complete", "agent_id": "maestro", "result": "Mission complete. Report generated."})

        # Feed the synthesized wiki entry back into the vector store so future missions
        # for this entity can recall this synthesis. Self-feeding knowledge base.
        if wiki_entry_markdown:
            try:
                synth_parsed = {
                    "chunk_id": wiki_chunk_id,
                    "filename": f"tangle-synthesis-{entity_name.lower().replace(' ', '-')[:40]}.md",
                    "filepath": f"synthesized/{wiki_chunk_id}.md",
                    "raw_content": wiki_entry_markdown,  # use the wiki-spec markdown as the raw content for vector embedding
                    "markdown": wiki_entry_markdown,
                    "confidence": self._confidence_from_critic(
                        evaluation.get("score"), evaluation.get("verified", False)
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "is_image": False,
                    "parse_error": None,
                }
                await self.vector_store.add_wiki_entry(synth_parsed, entity_name)
                self._emit({"type": "wiki_entry_added", "chunk_id": wiki_chunk_id, "entity": entity_name})
                logger.info(f"Re-ingested synthesized wiki entry {wiki_chunk_id} for entity {entity_name}")
            except Exception as e:
                logger.error(f"Failed to re-ingest synthesized wiki entry: {e}")

        # Pull usage stats for this mission from the gateway
        usage = self.gateway.get_mission_usage(mission_id) if hasattr(self.gateway, "get_mission_usage") else {}

        # Refresh the Obsidian-compatible wiki vault so docs/wiki/ stays in sync
        # with whatever just landed in SQLite (original upload + synthesized entry).
        # Best-effort: a vault export failure must not break the mission response.
        wiki_export_summary: Optional[Dict[str, Any]] = None
        if export_on_mission_enabled():
            try:
                wiki_export_summary = self.wiki_vault.export_all()
                self._emit({
                    "type": "wiki_vault_exported",
                    "vault_root": wiki_export_summary.get("vault_root"),
                    "chunks": wiki_export_summary.get("chunks"),
                    "entities": wiki_export_summary.get("entities"),
                })
            except Exception as e:
                logger.warning(f"Wiki vault auto-export after mission failed: {e}")

        self._running = False
        return {
            "mission_id": mission_id,
            "entity_name": entity_name,
            # Backwards compat: frontend reads `data.report` and parses the wiki-nodes JSON block
            "report": final_report,
            # New: explicit dual-output fields
            "report_markdown": final_report,
            "wiki_entry_markdown": wiki_entry_markdown,
            "wiki_entry_chunk_id": wiki_chunk_id,
            # Source-of-truth fields
            "wiki_entry": wiki_entry,  # the originally uploaded file's wiki entry (if any)
            "verified": evaluation.get("verified", False),
            "critic_score": evaluation.get("score"),
            "critic_critique": evaluation.get("critique"),
            "usage": usage,
            "wiki_export": wiki_export_summary,
        }

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
        self._running = False
