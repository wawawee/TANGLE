"""Mission phase executors for TANGLE.

Extracts the monolithic run_mission() into composable phases:
- PlanningPhase: decompose mission into research subtasks
- ResearchPhase: Scout + Librarian parallel execution
- EvaluationPhase: Critic gate with conditional branching
- SynthesisPhase: dual-output report + wiki entry
- IngestionPhase: re-ingest synthesized entry + vault export

Each phase is independently testable and enables concurrent missions.
Conditional branching: if critic score < threshold and iterations remain,
the loop re-enters ResearchPhase with critic feedback as context.
"""

import os
import re
import json
import uuid
import time
import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

import guardrails
from contradiction_engine import analyze_contradictions

logger = logging.getLogger("tangle.phases")

# Import metrics (will be available after metrics.py is created)
try:
    import metrics as tangle_metrics
except ImportError:
    tangle_metrics = None


# ── Entity type heuristics (no LLM cost) ────────────────────────

_COMPANY_SUFFIXES = [
    "ab", "abp", "ltd", "llc", "gmbh", "inc", "corp", "corporation",
    "sa", "nv", "bv", "plc", "ag", "kg", "ohg", "sarl", "spa",
    "aps", "sdn bhd", "pty", "ltd.", "inc.", "llp",
]
_LEGAL_FORM_PREFIXES = ["ab ", "abp ", "gmbh ", "sa ", "nv ", "bv "]


def _detect_entity_type(entity_name: str) -> str:
    """Determine likely entity type using heuristics.

    Returns one of: 'company', 'person', 'domain', 'product', 'general'.
    No LLM call — pure pattern matching.
    """
    name = entity_name.strip().lower()

    # Domain / URL
    if re.match(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.[a-z]{2,}$", name) or \
       re.match(r"^https?://", name):
        return "domain"

    # Company indicators
    for suffix in _COMPANY_SUFFIXES:
        if name.endswith(f" {suffix}") or name.endswith(f".{suffix}"):
            return "company"
    for prefix in _LEGAL_FORM_PREFIXES:
        if name.startswith(prefix):
            return "company"
    if re.search(r"\b(?:corp|limited|incorporated|company|group|holdings?|ventures|partners)\b", name):
        return "company"

    # Person indicators: "FirstName LastName" pattern (2-4 words, capitalized)
    words = name.split()
    if 2 <= len(words) <= 4 and all(w[0].isupper() if w else False for w in words):
        if not any(w in name for w in ["ab ", "ltd", "inc"]):
            return "person"

    return "general"


@dataclass
class MissionContext:
    """Shared state passed between phases.

    Immutable per-phase: phases return new context or modify in place.
    """
    mission_id: str
    entity_name: str
    uploaded_filepath: Optional[str] = None
    wiki_entry: Optional[Dict[str, Any]] = None
    plan: str = ""
    findings: List[str] = field(default_factory=list)
    evaluation: Dict[str, Any] = field(default_factory=dict)
    report_markdown: str = ""
    wiki_entry_markdown: str = ""
    wiki_entry_chunk_id: str = ""
    wiki_export_summary: Optional[Dict[str, Any]] = None
    execution_plan: str = ""
    usage: Dict[str, Any] = field(default_factory=dict)
    selected_skills: List[Tuple[str, float]] = field(default_factory=list)
    skill_context: str = ""
    entity_type: str = "general"
    iteration_count: int = 0
    max_iterations: int = 3
    loop_feedback: str = ""
    evidence_texts: List[Dict[str, str]] = field(default_factory=list)
    contradiction_result: Optional[Dict[str, Any]] = None


class MissionPhase(ABC):
    """Base class for mission phases.

    Each phase receives a MissionContext and returns the (possibly modified) context.
    Phases are composable and independently testable.
    """

    def __init__(self, orchestrator: "AgentOrchestrator"):
        self.orch = orchestrator

    @abstractmethod
    async def execute(self, ctx: MissionContext) -> MissionContext:
        """Run this phase. Returns updated context."""
        ...

    def _emit(self, event: Dict[str, Any]):
        """Forward event emission to orchestrator."""
        self.orch._emit(event)

    def _ctx(self) -> dict:
        """Build agent_context dict for gateway calls."""
        return self.orch._ctx()


class PlanningPhase(MissionPhase):
    """Phase 2: Decompose mission into research subtasks.

    Uses the Planner agent to generate a research plan based on
    the entity name and any ingested file content.
    Detects entity type heuristically (no LLM cost) to guide phase execution.
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        ctx.entity_type = _detect_entity_type(ctx.entity_name)
        self._emit({
            "type": "entity_type_detected",
            "entity_type": ctx.entity_type,
            "entity_name": ctx.entity_name,
        })
        logger.info(f"Entity type detected: {ctx.entity_type} for '{ctx.entity_name}'")

        self._emit({"type": "agent_think", "agent_id": "planner", "turn": 1})

        plan_prompt = f"Develop a plan to research ways to help '{ctx.entity_name}'."
        if ctx.wiki_entry:
            plan_prompt += f" We have ingested files containing: {ctx.wiki_entry['raw_content'][:500]}"
        if ctx.loop_feedback:
            plan_prompt += (
                f"\n\nThis is iteration {ctx.iteration_count + 1}/{ctx.max_iterations}. "
                f"Previous research was critiqued as: {ctx.loop_feedback[:500]}"
                f"\n\nFocus on addressing the gaps identified above."
            )

        planner_prompt = self.orch.AGENT_DEFS["planner"]["prompt"].format(entity=ctx.entity_name)
        if ctx.skill_context:
            planner_prompt = f"{ctx.skill_context}\n\n{planner_prompt}"
        messages = [
            {"role": "system", "content": planner_prompt},
            {"role": "user", "content": plan_prompt}
        ]

        # Record provider metrics
        start_time = time.time()
        resp = await self.orch.gateway.chat(self.orch.default_model, messages, agent_context=self._ctx())
        duration = time.time() - start_time

        if tangle_metrics:
            provider = self.orch.default_model.split("/")[0] if "/" in self.orch.default_model else "unknown"
            tangle_metrics.record_provider_call(provider, duration, "success")

        ctx.plan = resp.get("content", "Research the entity.")

        # Post-guardrail: sanitize
        safe_plan, _ = guardrails.apply_post_guardrail("planner", ctx.plan)
        ctx.plan = safe_plan

        self._emit({"type": "agent_complete", "agent_id": "planner", "result": ctx.plan[:400] + "..."})
        return ctx


class ResearchPhase(MissionPhase):
    """Phase 3: Dispatch Scout and Librarian in parallel.

    Scout searches the web; Librarian queries the internal wiki.
    Both run concurrently when a wiki entry exists.
    Guardrails applied post-agent to sanitize and validate outputs.
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Dispatching Research Agents"})

        # Skip librarian for entity types that don't have uploaded docs
        skip_librarian = not ctx.wiki_entry
        if ctx.entity_type == "domain":
            self._emit({"type": "event_log", "entry": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO", "agent": "System",
                "message": f"Entity type is '{ctx.entity_type}' — no internal wiki lookup needed"
            }})

        scout_feedback = ""
        if ctx.loop_feedback:
            scout_feedback = (
                f"Previous research was critiqued as insufficient. "
                f"Critique: {ctx.loop_feedback[:800]}\n\n"
                f"Perform DEEPER research targeting the gaps above."
            )

        scout_task = self.orch.delegate(
            scout_feedback or f"Search for external background, vulnerabilities, and solutions for {ctx.entity_name}.",
            "scout",
            ctx.entity_name,
            skill_context=ctx.skill_context,
        )

        tasks = [scout_task]
        if ctx.wiki_entry and not skip_librarian:
            lib_task = self.orch.delegate(
                f"Extract all relevant help insights and details for {ctx.entity_name} from the uploaded documents.",
                "librarian",
                ctx.entity_name,
                skill_context=ctx.skill_context,
            )
            tasks.append(lib_task)

        results = await asyncio.gather(*tasks)
        ctx.findings = list(results)

        # Apply post-guardrails to all findings
        sanitized = []
        for f in ctx.findings:
            safe, _ = guardrails.apply_post_guardrail("scout", f)
            sanitized.append(safe)
        ctx.findings = sanitized

        # Capture evidence texts for contradiction analysis
        ctx.evidence_texts = []
        for i, finding in enumerate(ctx.findings):
            ctx.evidence_texts.append({
                "source": f"scout-{i}",
                "text": finding[:2000],
            })

        return ctx


class EvaluationPhase(MissionPhase):
    """Phase 4: Critic evaluation gate with conditional branching.

    If the critic score is below threshold and iterations remain,
    the loop re-enters ResearchPhase with critic feedback as context.
    This creates an adaptive pipeline: plan → research → evaluate →
    (loop if score < threshold) → synthesize → ingest.

    Key differences from simple retry:
    - Full re-entry through PlanningPhase (not just scout retry)
    - Planner sees the critique and adjusts the research plan
    - Iteration count tracked to prevent infinite loops
    - Exponential backoff between iterations
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Evaluating gathered facts"})

        crit_threshold = float(os.getenv("TANGLE_CRITIC_THRESHOLD", "0.7"))
        max_iter = int(os.getenv("TANGLE_ORCHESTRATOR_MAX_RETRIES", "3"))

        combined_text = "\n\n".join(ctx.findings)
        ctx.evaluation = await self.orch.evaluate(
            combined_text,
            f"Does this content explain the situation of '{ctx.entity_name}' and provide concrete ways to help?",
            threshold=crit_threshold,
        )

        # Post-guardrail: validate critic output
        critic_text = json.dumps(ctx.evaluation)
        guardrails.apply_post_guardrail("critic", critic_text)

        # Conditional branching loop: re-enter research if score too low
        while not ctx.evaluation["passed"] and ctx.iteration_count < max_iter:
            ctx.iteration_count += 1
            backoff_s = 2 ** (ctx.iteration_count - 1)

            logger.info(
                f"Conditional branch: critic score {ctx.evaluation.get('score', 0):.2f} "
                f"< {crit_threshold} (iteration {ctx.iteration_count}/{max_iter}). "
                f"Re-entering research phase in {backoff_s}s."
            )
            self._emit({
                "type": "conditional_branch",
                "from": "evaluation",
                "to": "research",
                "reason": f"critic_score {ctx.evaluation.get('score', 0):.2f} < {crit_threshold}",
                "iteration": ctx.iteration_count,
                "critique": ctx.evaluation.get("critique", "")[:200],
            })
            self._emit({
                "type": "workflow_step", "agent_id": "maestro",
                "task": f"Branching back to research (iter {ctx.iteration_count}/{max_iter}): "
                        f"{ctx.evaluation.get('critique', '')[:120]}"
            })

            await asyncio.sleep(backoff_s)

            # Store critique as loop_feedback for next planning pass
            ctx.loop_feedback = ctx.evaluation.get("critique", "")

            # Re-enter PlanningPhase with the critique as context
            planner = PlanningPhase(self.orch)
            ctx = await planner.execute(ctx)

            # Re-enter ResearchPhase with focused critique
            researcher = ResearchPhase(self.orch)
            ctx = await researcher.execute(ctx)

            # Re-evaluate with expanded findings
            combined_text = "\n\n".join(ctx.findings)
            ctx.evaluation = await self.orch.evaluate(
                combined_text,
                f"Does this content explain the situation of '{ctx.entity_name}' and provide concrete ways to help?",
                threshold=crit_threshold,
            )
            guardrails.apply_post_guardrail("critic", json.dumps(ctx.evaluation))

        if not ctx.evaluation["passed"]:
            logger.warning(
                f"Evaluation gate still failing after {max_iter} iterations. "
                f"Continuing with best-effort synthesis."
            )
            self._emit({
                "type": "workflow_step", "agent_id": "maestro",
                "task": f"Gate still failing after {max_iter} iterations. Using best-effort."
            })

        return ctx


class SynthesisPhase(MissionPhase):
    """Phase 5: Synthesize final dual-output (report + wiki entry).

    Before synthesis, asks user to choose between solution approaches
    when multiple viable paths exist. Falls back to generating options
    from findings if none provided.
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Synthesizing master report"})

        # Generate solution approaches for user to choose from
        options = await self._generate_solution_options(ctx)

        if len(options) > 1:
            self._emit({"type": "event_log", "entry": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO", "agent": "System",
                "message": f"Generated {len(options)} solution approaches — awaiting user choice"
            }})
            chosen_id = await self.orch.request_decision(
                mission_id=ctx.mission_id,
                title="Choose a Solution Approach",
                description="Based on the research, I've identified multiple viable paths forward. Pick one to shape the final report.",
                options=options,
            )
            chosen = next((o for o in options if o["id"] == chosen_id), options[0])
            ctx.execution_plan = chosen.get("title", "")
            self._emit({"type": "event_log", "entry": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "INFO", "agent": "System",
                "message": f"User chose: {chosen['title']}"
            }})

        synth_result = await self.orch.synthesize(
            ctx.findings,
            ctx.entity_name,
            critic_score=ctx.evaluation.get("score"),
            verified=ctx.evaluation.get("verified", False),
            skill_context=ctx.skill_context,
        )

        ctx.report_markdown = synth_result["report_markdown"]
        ctx.wiki_entry_markdown = synth_result["wiki_entry_markdown"]
        ctx.wiki_entry_chunk_id = synth_result["wiki_entry_chunk_id"]

        # Post-guardrail: validate synth output structure
        guardrails.apply_post_guardrail("synthesizer", ctx.report_markdown)

        return ctx

    async def _generate_solution_options(self, ctx: MissionContext) -> list[dict]:
        """Use the orchestrator's delegate to generate solution approaches from findings."""
        if not ctx.findings or len(ctx.findings) < 50:
            return [{
                "id": "default",
                "title": "Standard Analysis",
                "summary": "Proceed with the default synthesis approach based on all collected findings.",
                "confidence": 0.85,
                "pros": ["Covers all evidence", "Balanced approach"],
                "cons": ["May lack specific strategic focus"],
            }]

        prompt = f"""Given these findings about "{ctx.entity_name}", suggest 2-3 distinct strategic approaches:

Findings:
{ctx.findings[:2000]}

For each approach, provide:
- A short title (3-6 words)
- A one-sentence summary
- 2-3 pros and 2-3 cons
- A confidence score (0.0-1.0)

Respond as JSON array: [{{"id":"str","title":"str","summary":"str","confidence":0.0,"pros":["str"],"cons":["str"]}}]"""

        try:
            result = await self.orch.gateway.chat(self.orch.default_model, [{"role": "user", "content": prompt}])
            text = result.get("content", "")
            # Extract JSON array from response
            import re
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                options = json.loads(match.group())
                if isinstance(options, list) and len(options) > 0:
                    return options
        except Exception as e:
            logger.warning(f"Failed to generate solution options: {e}")

        return [{
            "id": "default",
            "title": "Standard Analysis",
            "summary": f"Comprehensive analysis of {ctx.entity_name} based on all gathered evidence.",
            "confidence": 0.85,
            "pros": ["Based on all findings", "Systematic approach"],
            "cons": ["Generic structure"],
        }]


class IngestionPhase(MissionPhase):
    """Phase 6: Post-mission ingestion and vault export.

    - Save mission to DB
    - Re-ingest synthesized wiki entry into vector store
    - Export Obsidian vault
    - Collect usage stats
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        # Save mission
        self.orch.vector_store.save_mission(ctx.mission_id, ctx.entity_name, ctx.report_markdown)
        self._emit({"type": "agent_complete", "agent_id": "maestro", "result": "Mission complete. Report generated."})

        # Re-ingest synthesized wiki entry (self-feeding knowledge base)
        if ctx.wiki_entry_markdown:
            try:
                synth_parsed = {
                    "chunk_id": ctx.wiki_entry_chunk_id,
                    "filename": f"tangle-synthesis-{ctx.entity_name.lower().replace(' ', '-')[:40]}.md",
                    "filepath": f"synthesized/{ctx.wiki_entry_chunk_id}.md",
                    "raw_content": ctx.wiki_entry_markdown,
                    "markdown": ctx.wiki_entry_markdown,
                    "confidence": self.orch._confidence_from_critic(
                        ctx.evaluation.get("score"), ctx.evaluation.get("verified", False)
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "is_image": False,
                    "parse_error": None,
                }
                await self.orch.vector_store.add_wiki_entry(synth_parsed, ctx.entity_name)
                self._emit({"type": "wiki_entry_added", "chunk_id": ctx.wiki_entry_chunk_id, "entity": ctx.entity_name})
                logger.info(f"Re-ingested synthesized wiki entry {ctx.wiki_entry_chunk_id} for entity {ctx.entity_name}")
            except Exception as e:
                logger.error(f"Failed to re-ingest synthesized wiki entry: {e}")

        # Collect usage stats
        ctx.usage = self.orch.gateway.get_mission_usage(ctx.mission_id) if hasattr(self.orch.gateway, "get_mission_usage") else {}

        # Export Obsidian vault (best-effort)
        from wiki_vault import export_on_mission_enabled
        if export_on_mission_enabled():
            try:
                ctx.wiki_export_summary = self.orch.wiki_vault.export_all()
                self._emit({
                    "type": "wiki_vault_exported",
                    "vault_root": ctx.wiki_export_summary.get("vault_root"),
                    "chunks": ctx.wiki_export_summary.get("chunks"),
                    "entities": ctx.wiki_export_summary.get("entities"),
                })
            except Exception as e:
                logger.warning(f"Wiki vault auto-export after mission failed: {e}")

        return ctx


class ContradictionPhase(MissionPhase):
    """Optional Phase 7: Run contradiction detection on gathered evidence.

    Uses the multi-pass contradiction engine to find intra-source,
    inter-source, and legal contradictions in the research findings.
    Can be toggled via TANGLE_CONTRADICTION_ENABLED env var.
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        enabled = os.getenv("TANGLE_CONTRADICTION_ENABLED", "0").strip() in ("1", "true", "yes")
        if not enabled:
            logger.info("Contradiction detection disabled (TANGLE_CONTRADICTION_ENABLED=0)")
            return ctx

        if not ctx.evidence_texts or len(ctx.evidence_texts) < 2:
            logger.info("Not enough evidence texts for contradiction analysis")
            return ctx

        self._emit({
            "type": "workflow_step", "agent_id": "maestro",
            "task": f"Analyzing {len(ctx.evidence_texts)} evidence sources for contradictions"
        })
        logger.info(f"ContradictionPhase: analyzing {len(ctx.evidence_texts)} evidence texts")

        try:
            embed_fn = None
            try:
                embed_fn = self.orch.vector_store.get_embeddings
            except Exception:
                pass

            jurisdiction = os.getenv("TANGLE_CONTRADICTION_JURISDICTION", "default")
            result = await analyze_contradictions(
                self.orch.gateway,
                ctx.evidence_texts,
                enable_legal=True,
                jurisdiction=jurisdiction,
                embed_fn=embed_fn,
            )
            ctx.contradiction_result = result

            thread_count = len(result.get("threads", []))
            if thread_count > 0:
                self._emit({
                    "type": "contradictions_found",
                    "count": thread_count,
                    "intra": result.get("total_intra", 0),
                    "inter": result.get("total_inter", 0),
                    "legal": result.get("total_legal", 0),
                })
                logger.info(f"ContradictionPhase: {thread_count} contradictions found")
            else:
                self._emit({
                    "type": "contradictions_found",
                    "count": 0,
                    "detail": "No contradictions detected",
                })
                logger.info("ContradictionPhase: no contradictions found")
        except Exception as e:
            logger.warning(f"Contradiction analysis failed (non-fatal): {e}")
            ctx.contradiction_result = {"error": str(e), "threads": []}

        return ctx


# Default phase pipeline for run_mission()
DEFAULT_PHASES = [
    PlanningPhase,
    ResearchPhase,
    EvaluationPhase,
    SynthesisPhase,
    IngestionPhase,
    ContradictionPhase,
]
