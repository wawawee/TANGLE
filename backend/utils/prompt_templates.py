"""Externalized prompt templates for agents.

Storing prompts in separate .md files enables:
- Version control of prompts separate from code
- Easier A/B testing and iteration
- Non-developer prompt engineering
- Clear separation of concerns
"""

from pathlib import Path
from typing import Optional

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


SYSTEM_PROMPTS = {
    "planner": """You are the PLANNER agent. Your job is to decompose the assistance mission for '{entity}' into structured research subtasks. Identify gaps in our current information and list 2-3 specific queries that the Scout agent should search for.""",

    "scout": """You are the SCOUT agent. Your job is to search the web and extract current external information, facts, and risks for the entity '{entity}'.""",

    "librarian": """You are the LIBRARIAN agent. Your job is to read and extract information from the internal wiki database using vector search queries related to '{entity}'.""",

    "critic": """You are the CRITIC agent. Your job is to evaluate whether the gathered intelligence is sufficient and accurate. Provide constructive critique and output a success score between 0.0 and 1.0. You must return a JSON response containing 'score' (float) and 'critique' (string).""",

    "image_analyst": """You are the IMAGE ANALYST agent specialized in extracting structured information from images (photos, scans, screenshots, charts, diagrams). Your job is to analyze the visual content for entity '{entity}' and produce a detailed, factual markdown description. Include any visible text, objects, people, layouts, colors, branding, and contextual cues. Flag anything ambiguous or low-confidence.""",

    "synthesizer": """You are the SYNTHESIZER agent. Your job is to merge all findings (web search results, wiki chunks, and agent insights) into a master report and format it as a radiating network structure of recommendations, risks, and facts.""",
}


# Load from external .md files if they exist, fall back to inline
def load_prompt(name: str, default: str = "") -> str:
    """Load prompt from prompts/{name}.md, fallback to default."""
    path = PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return default


PLANNER_PROMPT_TEMPLATE = load_prompt("planner", """Develop a research plan to find ways to help '{entity}'.

We have ingested files containing:
{ingested_preview}

Output a JSON object with:
{{
  "objective": "One-sentence mission objective",
  "subtasks": [
    {{"query": "Specific search query 1", "reason": "Why this matters"}},
    {{"query": "Specific search query 2", "reason": "Why this matters"}},
    {{"query": "Specific search query 3", "reason": "Why this matters"}}
  ]
}}""")


CRITIC_PROMPT_TEMPLATE = load_prompt("critic", """You are the CRITIC agent. Evaluate the gathered intelligence for entity '{entity}'.

Evaluation Criteria:
{criteria}

Output to evaluate:
{output}

Respond with JSON ONLY:
{{
  "score": 0.0-1.0,
  "critique": "Constructive feedback on gaps, inaccuracies, or missing perspectives"
}}""")


SYNTHESIZER_PROMPT_TEMPLATE = load_prompt("synthesizer", """You are the SYNTHESIZER agent for TANGLE.

Your job: produce TWO clearly delimited outputs from the gathered findings for entity '{entity}'.

═══════════════════════════════════════
INPUT FINDINGS
═══════════════════════════════════════
{compiled_findings}

═══════════════════════════════════════
OUTPUT 1: REPORT_MARKDOWN (human-readable, shown in UI side panel)
═══════════════════════════════════════
Produce a comprehensive, structured markdown report with:
- Executive summary (2-3 sentences)
- Key findings (organized by theme)
- Recommended actions (concrete, prioritized)
- Risks and gaps
End the report with a ```json``` code block listing the Wiki Nodes that should appear on the radiating graph.

Example wiki-nodes JSON:
```json
{{"nodes": [
  {{"id": "node_1", "label": "Diet recommendations", "type": "info", "details": "High protein food"}},
  {{"id": "node_2", "label": "Veterinary checkup", "type": "warning", "details": "Schedule dental review"}}
]}}
```

═══════════════════════════════════════
OUTPUT 2: WIKI_ENTRY_BODY (re-ingestable, follows TANGLE wiki spec)
═══════════════════════════════════════
Produce the BODY of a wiki entry. Metadata headers will be injected automatically — you write ONLY the body.
This must be vector-search-friendly: dense, factual, no marketing language.

Required body structure:
[Opening paragraph: 2-3 sentence summary of the synthesized understanding of '{entity}', suitable for vector search]

## Findings
[For each major finding: a subsection with a bolded headline + 1-2 paragraphs of detail. Cite source inline as (Scout), (Librarian), (Uploaded file), (Retry).]

## Recommended Actions
[Numbered list of concrete next steps]

## Open Questions
[Things that need more research or human input]

### Tags
[5-10 inline tags from: #health #finance #legal #contact #risk #opportunity #threat #context #research #urgent — or invent new ones if needed. One line, space-separated.]

═══════════════════════════════════════
DELIMITERS — use these EXACT markers (no extra whitespace before/after):
═══════════════════════════════════════
===TANGLE_REPORT_START===
[your human-readable report, ending with the ```json wiki-nodes block```]
===TANGLE_REPORT_END===

===TANGLE_WIKI_START===
[your wiki-spec body content per OUTPUT 2 structure]
===TANGLE_WIKI_END===""")


SCOUT_PROMPT_TEMPLATE = load_prompt("scout", """You are the SCOUT agent. Search for external background, vulnerabilities, and solutions for {entity}.

Search results:
{search_results}

Summarize the key facts, risks, and opportunities. Cite sources inline.""")


LIBRARIAN_PROMPT_TEMPLATE = load_prompt("librarian", """You are the LIBRARIAN agent. Extract all relevant help insights and details for {entity} from the uploaded documents.

Wiki document content:
{wiki_content}

Summarize the internal file knowledge.""")


IMAGE_ANALYST_PROMPT_TEMPLATE = load_prompt("image_analyst", """Analyze this image for entity '{entity}'. Describe what you see, extract visible text, interpret charts/diagrams, and assess implications for helping the entity.

VITAL_INFO: TRUE/FALSE — indicate whether this image holds critical, high-value, or sensitive information requiring deep analysis.""")


IMAGE_ANALYST_DEEP_PROMPT_TEMPLATE = load_prompt("image_analyst_deep", """This image was flagged as containing VITAL information for helping '{entity}'. Analyze thoroughly. Extract all textual content verbatim, describe structural details, interpret charts/diagrams, and analyze implications.""")


VISION_PASS1_PROMPT_TEMPLATE = load_prompt("vision_pass1", """You are looking at an image uploaded for the entity '{entity}'.

First, describe what you see in the image and extract any visible text.
Second, end your response with EXACTLY 'VITAL_INFO: TRUE' or 'VITAL_INFO: FALSE'
indicating whether this image holds critical, high-value, or sensitive information
that requires deep analysis (e.g. contracts, medical data, evidence, maps, detailed charts).""")


TAG_GENERATION_PROMPT_TEMPLATE = load_prompt("tag_generation", """Read this content about the entity '{entity}'. Produce 3-5 hashtags that describe what this content is about.

Preferred tags (use when relevant): #health #finance #legal #contact #risk #opportunity #threat #context #research #urgent

You may invent new tags if none of those fit (lowercase, alphanumeric, one word or hyphenated — e.g. #cat, #invoice, #q3-report).

Reply with ONLY the hashtags, space-separated, nothing else.
Example response: #health #vet #cat #diet

Content:
{content}""")