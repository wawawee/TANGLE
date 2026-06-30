"""Contradiction Engine — detects conflicting claims across evidence sources.

Adapted from the LAGA project's ANALYZE_SYSTEM_PROMPT into a standalone
module for TANGLE.  Three contradiction kinds:
  - intra_source :  same source contradicts itself
  - inter_source :  two different sources conflict
  - legal        :  a statement contradicts known Swedish law (SFS)
"""

import json
import logging
from typing import Any

logger = logging.getLogger("tangle.contradiction_engine")

CONTRADICTION_SYSTEM_PROMPT = """You are a contradiction detection engine for legal/evidence analysis.
Analyse the provided evidence texts and find contradictions between statements.

Return JSON only matching this schema:
{
  "contradictions": [
    {
      "kind": "intra_source" | "inter_source" | "legal",
      "confidence": 0.0-1.0,
      "severity": "low" | "medium" | "high",
      "claim_excerpt": "the exact text of the claim",
      "claim_source": "which evidence file or speaker this comes from",
      "conflicts_with_excerpt": "the exact text that contradicts",
      "conflicts_with_source": "which evidence file, speaker, or law reference",
      "explanation": "Short explanation of why this is a contradiction"
    }
  ],
  "summary": "One-paragraph summary of the contradiction landscape",
  "key_claims": ["string", "string"]
}

Rules:
- Use kind "intra_source" when the SAME evidence source contradicts itself.
- Use kind "inter_source" when TWO DIFFERENT sources conflict.
- Use kind "legal" when a statement contradicts Swedish law (SFS number + paragraph).
- Only flag contradictions that are clearly supported by the evidence text.
- If uncertain about a contradiction, lower the confidence score.
- severity "high" = critical contradiction that affects the core case.
- severity "medium" = notable but not decisive.
- severity "low" = minor inconsistency.
- Keep explanations concise and factual.
- Maximum 15 contradictions per analysis."""


async def analyze_contradictions(
    gateway: Any,
    evidence_texts: list[dict[str, str]],
) -> dict:
    """Run contradiction analysis on a list of evidence items.

    Args:
        gateway: FreeGateway instance for LLM calls.
        evidence_texts: list of {source, text} dicts.

    Returns:
        dict with contradictions array + summary.
    """
    if not evidence_texts:
        return {"contradictions": [], "summary": "No evidence to analyse.", "key_claims": []}

    evidence_block = ""
    for i, item in enumerate(evidence_texts, 1):
        source = item.get("source", f"evidence_{i}")
        text = item.get("text", "")
        evidence_block += f"\n=== Source: {source} ===\n{text}\n"

    if len(evidence_block) > 18000:
        evidence_block = evidence_block[:18000] + "\n\n[...truncated]"

    messages = [
        {"role": "system", "content": CONTRADICTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Analyse the following evidence texts for contradictions:\n\n{evidence_block}",
        },
    ]

    result = await gateway.chat(
        "openrouter/meta-llama/llama-3.3-70b-instruct:free", messages
    )

    content = result.get("content", "")
    if not content:
        logger.warning("Contradiction analysis returned empty content")
        return {
            "contradictions": [],
            "summary": "Analysis failed — no response from model.",
            "key_claims": [],
        }

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Contradiction analysis returned non-JSON: {content[:200]}")
        return {
            "contradictions": [],
            "summary": "Analysis returned invalid JSON.",
            "key_claims": [],
        }

    contradictions = parsed.get("contradictions", [])
    summary = parsed.get("summary", "Analysis complete.")
    key_claims = parsed.get("key_claims", [])

    if not isinstance(contradictions, list):
        contradictions = []

    validated = []
    for c in contradictions:
        if c.get("kind") not in ("intra_source", "inter_source", "legal"):
            continue
        validated.append(
            {
                "kind": c["kind"],
                "confidence": min(max(float(c.get("confidence", 0.5)), 0.0), 1.0),
                "severity": c.get("severity", "medium")
                if c.get("severity") in ("low", "medium", "high")
                else "medium",
                "claim_excerpt": str(c.get("claim_excerpt", ""))[:500],
                "claim_source": str(c.get("claim_source", "unknown"))[:200],
                "conflicts_with_excerpt": str(c.get("conflicts_with_excerpt", ""))[:500],
                "conflicts_with_source": str(c.get("conflicts_with_source", "unknown"))[:200],
                "explanation": str(c.get("explanation", ""))[:500],
            }
        )

    total = len(validated)
    by_kind: dict[str, int] = {}
    for c in validated:
        by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1

    logger.info(
        f"Contradiction analysis: {total} found "
        f"(intra_source={by_kind.get('intra_source', 0)}, "
        f"inter_source={by_kind.get('inter_source', 0)}, "
        f"legal={by_kind.get('legal', 0)})"
    )

    return {
        "contradictions": validated,
        "summary": summary,
        "key_claims": key_claims,
    }


def format_contradiction_report(contradictions: list[dict]) -> str:
    """Format contradictions as human-readable markdown."""
    if not contradictions:
        return "No contradictions detected."

    lines = ["## Contradiction Analysis\n"]

    for i, c in enumerate(contradictions, 1):
        kind_icon = {"intra_source": "🔁", "inter_source": "⚡", "legal": "⚖️"}
        icon = kind_icon.get(c["kind"], "•")
        lines.append(
            f"### {icon} Contradiction #{i} ({c['kind'].replace('_', ' ').title()})\n"
        )
        lines.append(f"- **Severity**: {c['severity'].upper()}")
        lines.append(f"- **Confidence**: {c['confidence']:.0%}")
        lines.append(f"- **Claim**: \"{c['claim_excerpt']}\"")
        lines.append(f"  — Source: *{c['claim_source']}*")
        lines.append(f"- **Conflicts With**: \"{c['conflicts_with_excerpt']}\"")
        lines.append(f"  — Source: *{c['conflicts_with_source']}*")
        lines.append(f"- **Explanation**: {c['explanation']}")
        lines.append("")

    return "\n".join(lines)
