"""Contradiction Engine v2 — multi-pass, embedding-assisted, three-way threading.

Pipeline:
  Pass 1 — Extract claims from all evidence texts via embedding similarity grouping.
  Pass 2 — Evaluate candidate pairs with LLM (cheap model) for contradictions.
  Pass 3 — Generate thread graph (claims → nodes, contradictions → edges).

Three contradiction kinds:
  - intra_source : same speaker/source contradicts itself
  - inter_source : two different sources/speakers conflict
  - legal        : a statement contradicts known law or regulation

Output includes a 'threads' array suitable for React Flow visualization:
  claims → nodes with text excerpts
  threads → colored edges (red=intra, orange=inter, blue=legal)
"""

import json
import logging
import re
import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("tangle.contradiction")

# ── Data Types ──────────────────────────────────────────────────

@dataclass
class Claim:
    """A single extracted claim from an evidence source."""
    id: str
    source: str
    speaker: str = ""
    text: str = ""
    excerpt: str = ""
    embedding: List[float] = field(default_factory=list)


@dataclass
class Thread:
    """A contradiction between two claims — becomes an edge in React Flow."""
    id: str
    kind: str  # "intra_source" | "inter_source" | "legal"
    severity: str  # "low" | "medium" | "high"
    from_claim_id: str
    to_claim_id: str
    from_excerpt: str
    to_excerpt: str
    explanation: str
    confidence: float = 0.5


@dataclass
class ContradictionResult:
    """Full contradiction analysis result, ready for frontend rendering."""
    claims: List[Dict[str, str]] = field(default_factory=list)
    threads: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    total_intra: int = 0
    total_inter: int = 0
    total_legal: int = 0


# ── Claim Extraction (Pass 1) ───────────────────────────────────

# Simple sentence splitter for evidence text
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Keywords that indicate a factual claim (vs narrative filler)
_CLAIM_INDICATORS = [
    "says", "stated", "claimed", "asserted", "confirmed", "testified",
    "according to", "admitted", "denied", "explained", "mentioned",
    "attests", "alleges", "maintains", "insists", "notes",
]

_MIN_CLAIM_LENGTH = 40
_MAX_CLAIMS_PER_SOURCE = 8


def _extract_claims_from_source(source: str, text: str, idx: int) -> List[Dict[str, str]]:
    """Extract claim-like sentences from a single evidence source.

    Uses heuristics: sentence splitting + claim indicator keywords.
    Returns list of {id, source, speaker, text, excerpt}.
    """
    claims: List[Dict[str, str]] = []
    sentences = _SENTENCE_SPLIT.split(text)

    speaker = source  # default: source name is the speaker
    # Try to extract a named speaker from the source field
    if " - " in source:
        parts = source.split(" - ", 1)
        speaker = parts[0].strip()
        source_name = parts[1].strip()
    else:
        source_name = source

    claim_count = 0
    for s in sentences:
        s = s.strip()
        if len(s) < _MIN_CLAIM_LENGTH:
            continue

        # Check if sentence looks like a factual claim
        is_claim = any(indicator in s.lower() for indicator in _CLAIM_INDICATORS)

        # Also accept any sentence that's a reasonable length and ends with period
        if not is_claim and len(s) < 80:
            continue

        claim_id = f"claim_{idx}_{claim_count}"
        excerpt = s[:200]
        if len(s) > 200:
            excerpt += "..."

        claims.append({
            "id": claim_id,
            "source": source_name,
            "speaker": speaker,
            "text": s,
            "excerpt": excerpt,
        })

        claim_count += 1
        if claim_count >= _MAX_CLAIMS_PER_SOURCE:
            break

    return claims


# ── Embedding-Based Pairing (Pass 1b) ───────────────────────────

def _text_fingerprint(text: str) -> str:
    """Create a content-based hash for deduplication."""
    normalized = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


async def _pair_claims(
    claims: List[Dict[str, str]],
    embed_fn,
) -> List[Tuple[Dict[str, str], Dict[str, str]]]:
    """Pair claims that are semantically related using embeddings.

    Only pairs that are similar enough might be contradictory.
    This avoids O(n²) LLM calls by pre-filtering with cheap embeddings.
    """
    if len(claims) < 2:
        return []

    # Get embeddings for all claims
    texts = [c["text"] for c in claims]
    try:
        embeddings = []
        for t in texts:
            emb = await embed_fn(t[:1000])
            embeddings.append(emb)
    except Exception as e:
        logger.warning(f"Embedding for claim pairing failed: {e}. Using sequential pairing.")
        # Fallback: pair each claim with 2-3 nearest neighbors by position
        pairs = []
        for i in range(len(claims)):
            for j in range(i + 1, min(i + 4, len(claims))):
                same_source = claims[i]["source"] == claims[j]["source"]
                same_speaker = claims[i]["speaker"] == claims[j]["speaker"]
                if same_source or same_speaker:
                    pairs.append((claims[i], claims[j]))
                else:
                    pairs.append((claims[i], claims[j]))
        return pairs

    # Cosine similarity pre-filter
    pairs = []
    seen_fingerprints: set = set()

    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            fp = _text_fingerprint(claims[i]["text"] + claims[j]["text"])
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)

            # Compute cosine similarity between claim embeddings
            ei = embeddings[i]
            ej = embeddings[j]
            if not ei or not ej:
                continue

            try:
                dot = sum(a * b for a, b in zip(ei[:128], ej[:128]))
                norm_i = sum(a * a for a in ei[:128]) ** 0.5
                norm_j = sum(a * a for a in ej[:128]) ** 0.5
                if norm_i == 0 or norm_j == 0:
                    continue
                similarity = dot / (norm_i * norm_j)
            except Exception:
                continue

            # Only pair claims with some semantic similarity (0.3-0.9 range)
            # Too low = unrelated, too high = same claim restated
            if 0.25 < similarity < 0.95:
                pairs.append((claims[i], claims[j]))

    return pairs


# ── LLM Evaluation (Pass 2) ─────────────────────────────────────

_ANALYSIS_PROMPT = """You are a contradiction detection engine. Analyse the pair of claims below and determine if they CONTRADICT each other.

Contradiction kinds:
  intra_source — SAME speaker/source contradicts themselves
  inter_source — TWO DIFFERENT speakers/sources contradict each other
  legal — a statement contradicts known law/regulation

IMPORTANT: Only flag real contradictions. Differences in emphasis or incomplete information are NOT contradictions.

Respond in JSON only:
{
  "is_contradiction": true/false,
  "kind": "intra_source" | "inter_source" | "legal",
  "severity": "low" | "medium" | "high",
  "explanation": "One sentence explanation",
  "confidence": 0.0-1.0
}

Claim A (from {source_a}):
"{claim_a}"

Claim B (from {source_b}):
"{claim_b}"

Is this a contradiction?"""

_LEGAL_CHECK_PROMPT = """You are a legal contradiction detector. Determine if the following claim contradicts known law, regulation, or legal principle.

Respond in JSON only:
{
  "is_contradiction": true/false,
  "law_reference": "Name of relevant law/regulation or 'none'",
  "explanation": "One sentence explanation of the contradiction",
  "confidence": 0.0-1.0,
  "severity": "low" | "medium" | "high"
}

Claim:
"{claim_text}"

Jurisdiction context: {jurisdiction}

Does this claim contradict known law?"""

_DEFAULT_JURISDICTION = "Swedish law (SFS), European Union law, and general legal principles"
_JURISDICTION_MAP = {
    "sweden": "Swedish law (SFS - Svensk författningssamling), EU law, UN conventions",
    "uae": "UAE Federal Law, Dubai laws (DIFC), ADGM regulations, Sharia principles, UAE Commercial Companies Law",
    "uk": "UK law (common law, statutes), Companies Act 2006, UK GDPR, Bribery Act 2010",
    "us": "US Federal law, state laws, SEC regulations, common law principles",
    "eu": "EU regulations and directives, GDPR, general principles of EU law",
    "default": "General legal principles, international law, human rights conventions, common legal standards across jurisdictions",
}


async def _evaluate_pair(
    gateway: Any,
    claim_a: Dict[str, str],
    claim_b: Dict[str, str],
    model: str,
) -> Optional[Thread]:
    """Evaluate a single claim pair for contradiction via LLM."""
    same_source = claim_a["source"] == claim_b["source"]
    same_speaker = claim_a["speaker"] == claim_b["speaker"]

    prompt = _ANALYSIS_PROMPT.format(
        source_a=f"{claim_a['speaker']} ({claim_a['source']})",
        source_b=f"{claim_b['speaker']} ({claim_b['source']})",
        claim_a=claim_a["excerpt"],
        claim_b=claim_b["excerpt"],
    )

    try:
        resp = await gateway.chat(model, [
            {"role": "system", "content": "You are a JSON-only assistant. Respond with valid JSON."},
            {"role": "user", "content": prompt},
        ])
        content = resp.get("content", "").strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
    except Exception as e:
        logger.debug(f"Claim pair evaluation failed: {e}")
        return None

    if not data.get("is_contradiction"):
        return None

    kind = data.get("kind", "inter_source")
    if same_source or same_speaker:
        kind = "intra_source"

    return Thread(
        id=f"thread_{claim_a['id']}_{claim_b['id']}",
        kind=kind,
        severity=data.get("severity", "medium"),
        from_claim_id=claim_a["id"],
        to_claim_id=claim_b["id"],
        from_excerpt=claim_a["excerpt"],
        to_excerpt=claim_b["excerpt"],
        explanation=data.get("explanation", "Contradiction detected"),
        confidence=min(max(float(data.get("confidence", 0.5)), 0.0), 1.0),
    )


async def _check_legal(
    gateway: Any,
    claim: Dict[str, str],
    model: str,
    jurisdiction: str = "default",
) -> Optional[Thread]:
    """Check a single claim against known law."""
    jur_text = _JURISDICTION_MAP.get(jurisdiction, _JURISDICTION_MAP["default"])
    prompt = _LEGAL_CHECK_PROMPT.format(
        claim_text=claim["excerpt"],
        jurisdiction=jur_text,
    )

    try:
        resp = await gateway.chat(model, [
            {"role": "system", "content": "You are a JSON-only assistant. Respond with valid JSON."},
            {"role": "user", "content": prompt},
        ])
        content = resp.get("content", "").strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
    except Exception as e:
        logger.debug(f"Legal check failed for claim {claim['id']}: {e}")
        return None

    if not data.get("is_contradiction"):
        return None

    law_ref = data.get("law_reference", "Unknown law")
    return Thread(
        id=f"thread_legal_{claim['id']}",
        kind="legal",
        severity=data.get("severity", "medium"),
        from_claim_id=claim["id"],
        to_claim_id="law",
        from_excerpt=claim["excerpt"],
        to_excerpt=law_ref,
        explanation=data.get("explanation", "Contradicts law"),
        confidence=min(max(float(data.get("confidence", 0.5)), 0.0), 1.0),
    )


# ── API ─────────────────────────────────────────────────────────

async def analyze_contradictions(
    gateway: Any,
    evidence_texts: List[Dict[str, str]],
    embed_fn=None,
    jurisdiction: str = "default",
    enable_legal: bool = True,
) -> Dict[str, Any]:
    """Run multi-pass contradiction analysis.

    Args:
        gateway: FreeGateway instance.
        evidence_texts: list of {source, text} dicts.
        embed_fn: async function(text) -> List[float]. If None, uses sequential fallback.
        jurisdiction: Jurisdiction context for legal checks. One of:
                     "sweden", "uae", "uk", "us", "eu", "default".
        enable_legal: Enable legal contradiction checks (Pass 3).

    Returns:
        Dict with claims, threads, summary, and counts.
    """
    if not evidence_texts:
        return {
            "claims": [], "threads": [], "summary": "No evidence to analyse.",
            "total_intra": 0, "total_inter": 0, "total_legal": 0,
        }

    # ── Pass 1: Extract claims from all sources ──────────────
    all_claims: List[Dict[str, str]] = []
    for i, item in enumerate(evidence_texts):
        source = item.get("source", f"evidence_{i}")
        text = item.get("text", "")
        if not text:
            continue
        claims = _extract_claims_from_source(source, text, i)
        all_claims.extend(claims)

    if not all_claims:
        return {
            "claims": [], "threads": [], "summary": "No claims extracted from evidence.",
            "total_intra": 0, "total_inter": 0, "total_legal": 0,
        }

    logger.info(f"Pass 1 complete: {len(all_claims)} claims from {len(evidence_texts)} sources")

    # ── Pass 2: Embedding-based pairing + LLM evaluation ────
    threads: List[Thread] = []
    model = "openrouter/meta-llama/llama-3.3-70b-instruct:free"

    # Pair semantically similar claims
    pair_fn = embed_fn or (lambda t: [])
    pairs = await _pair_claims(all_claims, pair_fn)
    logger.info(f"Pass 1b complete: {len(pairs)} candidate claim pairs for evaluation")

    # Evaluate each pair with LLM
    for pair in pairs:
        thread = await _evaluate_pair(gateway, pair[0], pair[1], model)
        if thread:
            threads.append(thread)

    logger.info(f"Pass 2 complete: {len(threads)} contradictions found via pair evaluation")

    # ── Pass 3: Legal contradiction checks ───────────────────
    if enable_legal:
        legal_count = 0
        for claim in all_claims[:10]:  # Limit to 10 legal checks
            thread = await _check_legal(gateway, claim, model, jurisdiction)
            if thread:
                threads.append(thread)
                legal_count += 1
        logger.info(f"Pass 3 complete: {legal_count} legal contradictions found")

    # ── Assemble result ──────────────────────────────────────
    # De-duplicate threads (same claims, same kind)
    seen_threads: set = set()
    unique_threads: List[Thread] = []
    for t in threads:
        key = (t.from_claim_id, t.to_claim_id, t.kind)
        if key in seen_threads:
            continue
        seen_threads.add(key)
        unique_threads.append(t)

    # Count by kind
    intra = sum(1 for t in unique_threads if t.kind == "intra_source")
    inter = sum(1 for t in unique_threads if t.kind == "inter_source")
    legal = sum(1 for t in unique_threads if t.kind == "legal")

    # Sort by confidence descending
    unique_threads.sort(key=lambda t: t.confidence, reverse=True)

    # Build summary
    if not unique_threads:
        summary = "No contradictions detected across all evidence sources."
    else:
        parts = []
        if intra:
            parts.append(f"{intra} intra-source (same speaker contradicts themselves)")
        if inter:
            parts.append(f"{inter} inter-source (different speakers disagree)")
        if legal:
            parts.append(f"{legal} legal (statements conflict with applicable law)")
        summary = f"Found {len(unique_threads)} contradictions: {', '.join(parts)}."

    # Add law node for legal threads
    claims_out = [{"id": c["id"], "source": c["source"], "speaker": c["speaker"], "excerpt": c["excerpt"]}
                  for c in all_claims]
    if legal > 0:
        claims_out.append({
            "id": "law",
            "source": "Legal Framework",
            "speaker": jurisdiction,
            "excerpt": f"Applicable law: {_JURISDICTION_MAP.get(jurisdiction, _JURISDICTION_MAP['default'])}",
        })

    return {
        "claims": claims_out,
        "threads": [asdict(t) for t in unique_threads],
        "summary": summary,
        "total_intra": intra,
        "total_inter": inter,
        "total_legal": legal,
    }


def format_contradiction_report(result: Dict[str, Any]) -> str:
    """Format contradiction analysis as human-readable markdown."""
    threads = result.get("threads", [])
    if not threads:
        return "No contradictions detected."

    lines = ["## Contradiction Analysis\n"]
    for i, t in enumerate(threads, 1):
        kind_icon = {"intra_source": "SAME", "inter_source": "CONFLICT", "legal": "LAW"}
        icon = kind_icon.get(t.get("kind", ""), "•")
        lines.append(
            f"### #{i} {icon} ({t.get('kind', 'unknown').replace('_', ' ').title()})\n"
        )
        lines.append(f"- **Severity**: {t.get('severity', 'medium').upper()}")
        lines.append(f"- **Confidence**: {t.get('confidence', 0):.0%}")
        lines.append(f"- **Claim A**: \"{t.get('from_excerpt', '')[:120]}\"")
        lines.append(f"- **Claim B**: \"{t.get('to_excerpt', '')[:120]}\"")
        lines.append(f"- **Explanation**: {t.get('explanation', '')}")
        lines.append("")

    lines.append(f"**Summary:** {result.get('summary', '')}")
    return "\n".join(lines)
