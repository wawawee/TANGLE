"""Mission phase executors for TANGLE.

Extracts the monolithic run_mission() into composable phases:
- PlanningPhase: decompose mission into research subtasks
- ResearchPhase: Scout + Librarian parallel execution
- EvaluationPhase: Critic gate with retry loop
- SynthesisPhase: dual-output report + wiki entry
- IngestionPhase: re-ingest synthesized entry + vault export

Each phase is independently testable and enables concurrent missions.
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

logger = logging.getLogger("tangle.phases")

# Import metrics (will be available after metrics.py is created)
try:
    import metrics as tangle_metrics
except ImportError:
    tangle_metrics = None


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
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        self._emit({"type": "agent_think", "agent_id": "planner", "turn": 1})

        plan_prompt = f"Develop a plan to research ways to help '{ctx.entity_name}'."
        if ctx.wiki_entry:
            plan_prompt += f" We have ingested files containing: {ctx.wiki_entry['raw_content'][:500]}"

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
        self._emit({"type": "agent_complete", "agent_id": "planner", "result": ctx.plan[:400] + "..."})
        return ctx


class ResearchPhase(MissionPhase):
    """Phase 3: Dispatch Scout and Librarian in parallel.

    Scout searches the web; Librarian queries the internal wiki.
    Both run concurrently when a wiki entry exists.
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Dispatching Research Agents"})

        scout_task = self.orch.delegate(
            f"Search for external background, vulnerabilities, and solutions for {ctx.entity_name}.",
            "scout",
            ctx.entity_name,
            skill_context=ctx.skill_context,
        )

        if ctx.wiki_entry:
            lib_task = self.orch.delegate(
                f"Extract all relevant help insights and details for {ctx.entity_name} from the uploaded documents.",
                "librarian",
                ctx.entity_name,
                skill_context=ctx.skill_context,
            )
            ctx.findings = list(await asyncio.gather(scout_task, lib_task))
        else:
            scout_result = await scout_task
            ctx.findings = [scout_result]

        return ctx


class EvaluationPhase(MissionPhase):
    """Phase 4: Critic evaluation gate with retry loop.

    If the critic score is below threshold, retries Scout with
    refined queries (exponential backoff).
    """

    async def execute(self, ctx: MissionContext) -> MissionContext:
        self._emit({"type": "workflow_step", "agent_id": "maestro", "task": "Evaluating gathered facts"})

        combined_text = "\n\n".join(ctx.findings)
        ctx.evaluation = await self.orch.evaluate(
            combined_text,
            f"Does this content explain the situation of '{ctx.entity_name}' and provide concrete ways to help?"
        )

        # Retry loop with exponential backoff
        max_retries = int(os.getenv("TANGLE_ORCHESTRATOR_MAX_RETRIES", "3"))
        retry_count = 0

        while not ctx.evaluation["passed"] and retry_count < max_retries:
            retry_count += 1
            backoff_s = 2 ** (retry_count - 1)  # 1s, 2s, 4s
            logger.info(
                f"Evaluation gate failed (attempt {retry_count}/{max_retries}). "
                f"Backing off {backoff_s}s before retry."
            )
            self._emit({
                "type": "workflow_step", "agent_id": "maestro",
                "task": f"Gate failed (attempt {retry_count}/{max_retries}). "
                        f"Retrying in {backoff_s}s: {ctx.evaluation['critique'][:80]}"
            })
            await asyncio.sleep(backoff_s)

            retry_findings = await self.orch.delegate(
                f"Perform deeper research based on this critique: {ctx.evaluation['critique']}",
                "scout",
                ctx.entity_name
            )
            ctx.findings.append(retry_findings)

            # Re-evaluate after retry
            combined_text = "\n\n".join(ctx.findings)
            ctx.evaluation = await self.orch.evaluate(
                combined_text,
                f"Does this content explain the situation of '{ctx.entity_name}' and provide concrete ways to help?"
            )

        if not ctx.evaluation["passed"]:
            logger.warning(
                f"Evaluation gate still failing after {max_retries} retries. "
                f"Continuing with best-effort synthesis."
            )
            self._emit({
                "type": "workflow_step", "agent_id": "maestro",
                "task": f"Gate still failing after {max_retries} retries. Using best-effort."
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


# Default phase pipeline for run_mission()
DEFAULT_PHASES = [
    PlanningPhase,
    ResearchPhase,
    EvaluationPhase,
    SynthesisPhase,
    IngestionPhase,
]
