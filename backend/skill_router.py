"""SkillRouter for TANGLE — embedding-based domain skill selection.

Loads skills from a directory of .md files with YAML frontmatter,
pre-computes embedding vectors, and selects top-k skills for a given
entity + objective using cosine similarity. No LLM call needed —
pure vector retrieval.

Usage:
    router = SkillRouter("./skills", embed_fn=vector_store.get_embeddings)
    selected = await router.select("Acme AB", "financial due diligence review")
    prompt = router.build_system_prompt(selected)
"""

import os
import re
import json
import math
import time
import hashlib
import logging
import functools
from pathlib import Path
from typing import List, Tuple, Optional, Callable, Awaitable, Dict, Any

logger = logging.getLogger("tangle.skill_router")

# ── YAML frontmatter parser (lightweight, no dependency) ──────

def _parse_frontmatter(text: str) -> Tuple[dict, str]:
    """Parse YAML frontmatter between --- delimiters.

    Returns (metadata_dict, body_text). Uses regex-based key: value parsing.
    Supports lists, nested dicts, and scalars.
    """
    meta = {}
    body = text

    m = re.match(r'^---\s*\n(.*?)\n---\s*\n?(.*)', text, re.DOTALL)
    if not m:
        return meta, body

    yaml_block = m.group(1)
    body = m.group(2)

    current_key = None
    current_list = None
    in_list = False

    for line in yaml_block.split('\n'):
        # Top-level key: value
        kv_match = re.match(r'^(\w[\w_]*):\s*(.*)', line)
        if kv_match:
            if in_list and current_key:
                meta[current_key] = current_list
                in_list = False
            current_key = kv_match.group(1)
            value = kv_match.group(2).strip()

            # Boolean
            if value.lower() == 'true':
                meta[current_key] = True
            elif value.lower() == 'false':
                meta[current_key] = False
            # List start
            elif value == '' or value == '[]':
                current_list = []
                in_list = True
            # String
            else:
                meta[current_key] = _parse_scalar(value)
            continue

        # List item
        list_match = re.match(r'^\s+-\s+(.*)', line)
        if list_match and in_list and current_key:
            current_list.append(_parse_scalar(list_match.group(1).strip()))
            continue

        # Nested dict item (skip for now, not needed for our YAML)

    # Flush list
    if in_list and current_key:
        meta[current_key] = current_list

    return meta, body


def _parse_scalar(value: str):
    """Parse a scalar YAML value."""
    # Quoted string
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    # Number
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass
    return value


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(av * bv for av, bv in zip(a, b))
    na = math.sqrt(sum(av * av for av in a))
    nb = math.sqrt(sum(bv * bv for bv in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class SkillRouter:
    """Embedding-based skill selection for TANGLE missions.

    Loads skills from .md files with YAML frontmatter, computes
    embedding vectors, and selects the most relevant skills for
    a given entity + objective using cosine similarity.
    """

    def __init__(
        self,
        skill_dir: str,
        embed_fn: Callable[..., Awaitable[List[float]]],
        threshold: float = 0.60,
        top_k: int = 5,
        cache_ttl: int = 3600,
    ):
        self.skill_dir = Path(skill_dir)
        self.embed_fn = embed_fn
        self.threshold = threshold
        self.top_k = top_k
        self.cache_ttl = cache_ttl

        self.skills: Dict[str, dict] = {}
        self._cache: Dict[str, Tuple[float, list]] = {}
        self._loaded = False

    async def _ensure_loaded(self):
        """Lazy-load skills and pre-compute vectors on first access."""
        if self._loaded:
            return

        if not self.skill_dir.exists():
            logger.warning(f"Skill directory not found: {self.skill_dir}")
            self._loaded = True
            return

        for fpath in sorted(self.skill_dir.glob("*.md")):
            if fpath.name in ("SKILL_ARCHITECTURE.md", "SKILL_TEMPLATE.md"):
                continue
            try:
                text = fpath.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(text)

                skill_id = meta.get("id", fpath.stem)
                meta["_file"] = str(fpath)
                meta["_body"] = body

                # Compute embedding vector from keywords
                keywords = meta.get("embedding_keywords", [])
                if keywords:
                    embed_text = ". ".join(keywords)
                    try:
                        vec = await self.embed_fn(embed_text)
                    except Exception as e:
                        logger.warning(f"Embedding failed for skill '{skill_id}': {e}")
                        vec = _text_fallback_vector(embed_text)
                else:
                    vec = []

                self.skills[skill_id] = {
                    "meta": meta,
                    "vector": vec,
                }
                logger.info(
                    f"Loaded skill '{skill_id}' ({meta.get('name', '?')}) "
                    f"- {len(keywords)} keywords, dim={len(vec)}"
                )
            except Exception as e:
                logger.error(f"Failed to load skill {fpath.name}: {e}")

        self._loaded = True
        logger.info(f"SkillRouter loaded {len(self.skills)} skills from {self.skill_dir}")

    async def select(
        self,
        entity: str,
        objective: str = "",
        threshold: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> List[Tuple[str, float]]:
        """Select top-k skills matching entity + objective.

        Returns list of (skill_id, similarity_score) tuples, sorted
        by score descending. Always includes skills with always_include=True.

        Results are cached per (entity, objective) hash for cache_ttl seconds.
        """
        await self._ensure_loaded()

        if not self.skills:
            return []

        t = threshold if threshold is not None else self.threshold
        k = top_k if top_k is not None else self.top_k

        # Check cache
        cache_key = hashlib.sha256(f"{entity}|{objective}".encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached:
            ts, result = cached
            if time.time() - ts < self.cache_ttl:
                return result

        # Compute query vector
        query_text = f"{entity} {objective}".strip()
        if not query_text:
            query_text = entity
        try:
            query_vec = await self.embed_fn(query_text)
        except Exception as e:
            logger.warning(f"Embedding failed for query '{query_text}': {e}")
            query_vec = _text_fallback_vector(query_text)

        scored = []
        for sid, skill in self.skills.items():
            # Always-included skills get max score
            if skill["meta"].get("always_include"):
                scored.append((sid, 1.0))
                continue

            sv = skill.get("vector")
            if not sv or not query_vec:
                continue

            sim = _cosine_similarity(query_vec, sv)
            if sim >= t:
                scored.append((sid, sim))

        # Sort by score descending, take top-k
        scored.sort(key=lambda x: x[1], reverse=True)
        result = scored[:k]

        # Cache result
        self._cache[cache_key] = (time.time(), result)

        logger.info(
            f"SkillRouter: '{entity}' | '{objective[:50]}' "
            f"→ selected {len(result)} skills: "
            f"{[s for s, _ in result]}"
        )
        return result

    def build_system_prompt(self, selected: List[Tuple[str, float]]) -> str:
        """Build system prompt prefix from selected skills.

        The output can be prepended to any agent's system prompt
        to inject domain knowledge.
        """
        if not selected:
            return ""

        parts = [
            "The following domain skills are active for this mission.",
            "Use this knowledge to guide your research, analysis, and reporting.\n"
        ]

        for sid, score in selected:
            skill = self.skills.get(sid)
            if not skill:
                continue
            meta = skill["meta"]
            body = meta.get("_body", "")

            # Extract Purpose section as a quick summary
            purpose = ""
            pm = re.search(r'## Purpose\s*\n(.*?)(?:\n##|\Z)', body, re.DOTALL)
            if pm:
                purpose = pm.group(1).strip()

            parts.append(f"--- Skill: {meta.get('name', sid)} (relevance: {score:.2f}) ---")
            if purpose:
                parts.append(purpose)
            parts.append("")

        return "\n".join(parts).strip()

    def get_mcps(self, selected: List[Tuple[str, float]]) -> list:
        """Collect MCP server names from selected skills."""
        mcps = []
        for sid, _ in selected:
            skill = self.skills.get(sid)
            if skill:
                mcps.extend(skill["meta"].get("mcps", []))
        return mcps

    def get_apis(self, selected: List[Tuple[str, float]]) -> list:
        """Collect API names from selected skills."""
        apis = []
        for sid, _ in selected:
            skill = self.skills.get(sid)
            if skill:
                apis.extend(skill["meta"].get("apis", []))
        return apis

    def get_tools(self, selected: List[Tuple[str, float]]) -> list:
        """Collect tool names from selected skills."""
        tools = []
        for sid, _ in selected:
            skill = self.skills.get(sid)
            if skill:
                tools.extend(skill["meta"].get("tools", []))
        return tools

    def get_active_skill_ids(self) -> List[str]:
        """Return list of all loaded skill IDs."""
        return list(self.skills.keys())

    def get_skill_info(self, skill_id: str) -> Optional[dict]:
        """Return metadata for a specific skill."""
        skill = self.skills.get(skill_id)
        if not skill:
            return None
        info = dict(skill["meta"])
        info.pop("_body", None)
        return info

    async def reload(self):
        """Reload all skills from disk, recompute vectors."""
        self.skills = {}
        self._cache = {}
        self._loaded = False
        await self._ensure_loaded()
        logger.info("SkillRouter reloaded")

    def invalidate_cache(self):
        """Clear selection cache without reloading skills."""
        self._cache = {}
        logger.debug("SkillRouter cache invalidated")


def _text_fallback_vector(text: str) -> List[float]:
    """Simple character-level hash-based fallback vector.

    Used when embedding API is unavailable. Produces a deterministic
    128-dimensional vector from the input text.
    """
    dim = 128
    vec = [0.0] * dim
    for i, ch in enumerate(text.encode("utf-8")):
        idx = i % dim
        vec[idx] += (ch / 255.0) * (1.0 / (1.0 + (i // dim)))
    # Normalize
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 1e-9:
        vec = [v / norm for v in vec]
    else:
        vec = [1.0 / math.sqrt(dim)] * dim
    return vec
