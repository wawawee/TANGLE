"""Input/output guardrails for TANGLE agents.

Pre-agent: validate entity names, objectives, file paths.
Post-agent: validate JSON structure, score ranges, output safety.
Per-agent: agent-specific rule sets for critic, scout, synthesizer.
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("tangle.guardrails")

# ── Allowlists ──────────────────────────────────────────────────

ALLOWED_ENTITY_PATTERN = re.compile(r"^[a-zA-Z0-9\s\.\,'\-\&\(\)]{1,200}$")
ALLOWED_FILENAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\.\-\s]{1,255}$")
HALLUCINATED_SCORE_PATTERN = re.compile(r"(?<![\w.])[0-9]\.[0-9]{2,}(?![\w.%])")
SCRIPT_TAG_PATTERN = re.compile(r"<script[\s>]", re.IGNORECASE)
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore all previous instructions", re.IGNORECASE),
    re.compile(r"forget everything", re.IGNORECASE),
    re.compile(r"you are now (?:free|ungoverned)", re.IGNORECASE),
    re.compile(r"system override", re.IGNORECASE),
    re.compile(r"output your (?:system|base) prompt", re.IGNORECASE),
]


# ── Input Guardrails ────────────────────────────────────────────

def sanitize_entity_name(name: str) -> str:
    """Strip dangerous characters, truncate to 200 chars."""
    cleaned = name.strip()[:200]
    if not cleaned:
        raise ValueError("Entity name cannot be empty")
    if re.search(r"[<>{}\\]", cleaned):
        cleaned = re.sub(r"[<>{}\\]", "", cleaned).strip()
        if not cleaned:
            raise ValueError("Entity name contains only invalid characters")
    return cleaned


def validate_objective(obj: str) -> str:
    """Validate and sanitize mission objective for prompt injection."""
    cleaned = obj.strip()[:2000]
    for pat in PROMPT_INJECTION_PATTERNS:
        if pat.search(cleaned):
            logger.warning(f"Prompt injection pattern detected in objective: {pat.pattern}")
            raise ValueError("Objective contains prohibited patterns")
    return cleaned


def validate_filepath(path: str) -> str:
    """Validate file path — no traversal, must be existing file."""
    if ".." in path:
        raise ValueError(f"Path traversal detected in: {path}")
    if not path or not isinstance(path, str):
        raise ValueError("File path must be a non-empty string")
    return path


def validate_upload_filename(filename: str) -> str:
    """Validate uploaded filename — no path separators, whitelist chars."""
    basename = filename.split("/")[-1].split("\\")[-1]
    if not ALLOWED_FILENAME_PATTERN.match(basename):
        safe = re.sub(r"[^a-zA-Z0-9_\.\-\s]", "_", basename)[:255]
        logger.warning(f"Sanitized unsafe filename: {basename} -> {safe}")
        return safe
    return basename


# ── Output Guardrails ───────────────────────────────────────────

def validate_json_output(text: str, required_fields: List[str]) -> Tuple[bool, Optional[Dict], str]:
    """Parse JSON from agent output and validate required fields exist.

    Returns (valid, parsed_dict_or_None, error_message).
    Tolerates markdown codeblock wrapping.
    """
    if not text or not isinstance(text, str):
        return False, None, "Empty or non-string output"

    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            candidate = parts[1]
            if candidate.startswith("json"):
                candidate = candidate[4:]
            cleaned = candidate.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return False, None, f"Invalid JSON: {e}"

    if not isinstance(data, dict):
        return False, None, f"Expected JSON object, got {type(data).__name__}"

    missing = [f for f in required_fields if f not in data]
    if missing:
        return False, data, f"Missing required fields: {missing}"

    return True, data, ""


def validate_score_in_range(score: Any, min_v: float = 0.0, max_v: float = 1.0) -> Tuple[bool, str]:
    """Validate a score value is a float within range."""
    try:
        val = float(score)
    except (TypeError, ValueError):
        return False, f"Score '{score}' is not a valid number"
    if val < min_v or val > max_v:
        return False, f"Score {val} out of range [{min_v}, {max_v}]"
    return True, ""


def strip_hallucinated_scores(text: str) -> str:
    """Remove standalone high-precision floats that look hallucinated.

    Catches patterns like "0.87" or "0.9342" that models sometimes
    fabricate as fake confidence scores in non-evaluation output.
    """
    def _replace(m):
        val = float(m.group(0))
        if val > 1.0:
            return m.group(0)
        return "[confidence redacted]"
    return HALLUCINATED_SCORE_PATTERN.sub(_replace, text)


def sanitize_markdown(text: str) -> str:
    """Remove dangerous HTML/script tags from markdown."""
    if SCRIPT_TAG_PATTERN.search(text):
        text = SCRIPT_TAG_PATTERN.sub("<!-- script tag removed -->", text)
    text = text.replace("\x00", "")
    return text


def truncate_content(text: str, max_chars: int = 15_000) -> str:
    """Truncate content to max_chars with a note."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n…truncated ({len(text) - max_chars} more chars)"


# ── Per-Agent Guardrails ────────────────────────────────────────

AGENT_GUARDRAILS: Dict[str, Dict[str, Any]] = {
    "planner": {
        "pre": [],
        "post": ["sanitize_markdown", "truncate"],
    },
    "scout": {
        "pre": [],
        "post": ["sanitize_markdown", "truncate"],
    },
    "librarian": {
        "pre": [],
        "post": ["sanitize_markdown", "truncate"],
    },
    "critic": {
        "pre": [],
        "post": ["validate_critic_output"],
    },
    "synthesizer": {
        "pre": [],
        "post": ["validate_synth_output"],
    },
    "image_analyst": {
        "pre": [],
        "post": ["sanitize_markdown", "truncate"],
    },
}


def validate_critic_output(text: str) -> Tuple[bool, str]:
    """Critic must return valid JSON with score and critique."""
    valid, data, err = validate_json_output(text, ["score", "critique"])
    if not valid:
        return False, f"Critic output invalid: {err}"
    score_ok, score_err = validate_score_in_range(data["score"])
    if not score_ok:
        return False, f"Critic score invalid: {score_err}"
    return True, ""


def validate_synth_output(text: str) -> Tuple[bool, str]:
    """Synthesizer must contain both report and wiki delimiters."""
    missing = []
    if "===TANGLE_REPORT_START===" not in text:
        missing.append("REPORT_START delimiter")
    if "===TANGLE_REPORT_END===" not in text:
        missing.append("REPORT_END delimiter")
    if "===TANGLE_WIKI_START===" not in text:
        missing.append("WIKI_START delimiter")
    if "===TANGLE_WIKI_END===" not in text:
        missing.append("WIKI_END delimiter")
    if missing:
        return False, f"Synthesizer output missing: {', '.join(missing)}"
    return True, ""


def apply_post_guardrail(agent_id: str, text: str) -> Tuple[str, List[str]]:
    """Apply all post-agent guardrails for a given agent type.

    Returns (sanitized_text, warnings).
    """
    warnings: List[str] = []
    rules = AGENT_GUARDRAILS.get(agent_id, {})
    for rule in rules.get("post", []):
        try:
            if rule == "sanitize_markdown":
                text = sanitize_markdown(text)
            elif rule == "truncate":
                text = truncate_content(text)
            elif rule == "validate_critic_output":
                valid, err = validate_critic_output(text)
                if not valid:
                    warnings.append(err)
            elif rule == "validate_synth_output":
                valid, err = validate_synth_output(text)
                if not valid:
                    warnings.append(err)
        except Exception as e:
            warnings.append(f"Guardrail '{rule}' failed: {e}")
    return text, warnings


def apply_pre_guardrail(entity_name: str, objective: str = "", filepath: str = "") -> List[str]:
    """Apply all pre-mission guardrails.

    Returns list of warnings (empty = all good, raises on hard failures).
    """
    warnings: List[str] = []
    try:
        sanitize_entity_name(entity_name)
    except ValueError as e:
        warnings.append(str(e))

    if objective:
        try:
            validate_objective(objective)
        except ValueError as e:
            warnings.append(str(e))

    if filepath:
        try:
            validate_filepath(filepath)
        except ValueError as e:
            warnings.append(str(e))

    return warnings
