"""Tag extraction and normalization utilities.

Single source of truth for inline tag parsing across:
- ParsingEngine (chunk tags)
- AgentOrchestrator (wiki body tags)
- WikiVault (index tags)
"""

import re
from typing import List, Set, Iterable


# Matches #tag at word boundary: preceded by start-of-string or whitespace
# Does NOT match: C#, F#, #5, #-invalid, #tag-with-emoji
TAG_REGEX = re.compile(r"(?:^|\s)#([a-z0-9][a-z0-9_-]{1,30})", re.IGNORECASE)


# Canonical taxonomy — prefer these when relevant
TAG_TAXONOMY: Set[str] = {
    "health", "finance", "legal", "contact", "risk",
    "opportunity", "threat", "context", "research", "urgent",
}


def extract_inline_tags(text: str, max_tags: int = 8) -> List[str]:
    """Extract unique #tags from markdown text.

    Args:
        text: Markdown content to scan
        max_tags: Cap on returned tags (default 8, matches vault index cap)

    Returns:
        Deduplicated lowercase tags in order of first appearance
    """
    if not text:
        return []

    found = TAG_REGEX.findall(text.lower())
    seen: Set[str] = set()
    unique: List[str] = []

    for tag in found:
        if tag not in seen:
            seen.add(tag)
            unique.append(tag)
            if len(unique) >= max_tags:
                break

    return unique


def normalize_tags(
    tags: Iterable[str],
    allow_new: bool = True,
    taxonomy: Set[str] = None,
    max_tags: int = 8,
) -> List[str]:
    """Normalize and deduplicate tags, optionally steering toward taxonomy.

    Args:
        tags: Raw tag tokens (with or without # prefix)
        allow_new: If True, allow tags outside taxonomy; if False, filter to taxonomy only
        taxonomy: Preferred tag set (defaults to TAG_TAXONOMY)
        max_tags: Cap on returned tags

    Returns:
        Sorted (taxonomy-first, then alpha) unique tags without # prefix
    """
    if taxonomy is None:
        taxonomy = TAG_TAXONOMY

    seen: Set[str] = set()
    normalized: List[str] = []

    for tag in tags:
        t = tag.lstrip("#").lower().strip()
        if not t:
            continue
        if not re.match(r"^[a-z0-9][a-z0-9_-]{0,30}$", t):
            continue
        if t in seen:
            continue
        if not allow_new and t not in taxonomy:
            continue
        seen.add(t)
        normalized.append(t)
        if len(normalized) >= max_tags:
            break

    # Sort: taxonomy tags first (alphabetical), then invented tags (alphabetical)
    taxonomy_tags = sorted([t for t in normalized if t in taxonomy])
    custom_tags = sorted([t for t in normalized if t not in taxonomy])
    return taxonomy_tags + custom_tags