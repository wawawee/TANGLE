"""Universal file ingestion & parsing engine for TANGLE"""

import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List

logger = logging.getLogger("tangle.parser")

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    logger.warning("markitdown not installed. Using simple fallback parsers.")

class ParsingEngine:
    def __init__(self, gateway=None):
        self.gateway = gateway
        self.mid = MarkItDown() if MARKITDOWN_AVAILABLE else None
        self.tag_model = "openrouter/nvidia/nemotron-nano-12b-v2-vl:free"

    # Fixed taxonomy that the tag-generation prompt steers the LLM toward.
    # Model may invent new tags outside this list when none fit.
    TAG_TAXONOMY = (
        "#health #finance #legal #contact #risk #opportunity "
        "#threat #context #research #urgent"
    )

    async def parse_file(self, filepath: str, entity_name: str) -> Dict[str, Any]:
        """
        Parses any file into structured markdown following the standard spec.
        Checks for images and triggers dual-pass vision processing.
        """
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        content = ""
        confidence = 0.9  # Default parser confidence
        parse_error: Optional[str] = None

        logger.info(f"Parsing file: {filename} ({ext}) for entity: {entity_name}")

        is_image = ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")

        if is_image:
            # Trigger vision pipeline
            content, confidence = await self._parse_image_vision(filepath, entity_name)
        elif MARKITDOWN_AVAILABLE and self.mid:
            try:
                # Markitdown handles docx, xlsx, pptx, pdf, html, zip, etc.
                result = self.mid.convert(filepath)
                content = result.text_content
            except Exception as e:
                logger.error(f"MarkItDown conversion failed for {filename}: {e}")
                content, parse_error = self._fallback_parse(filepath)
                confidence = 0.5
        else:
            content, parse_error = self._fallback_parse(filepath)
            # Unify low-info confidence: 0.5 regardless of whether markitdown is installed
            if ext not in (".txt", ".md"):
                confidence = 0.5

        # Generate structured markdown spec
        chunk_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Auto-tag via cheap LLM. Falls back to ['untagged'] on any failure
        # (no gateway, LLM error, malformed output). Cost discipline: single
        # call with a short prompt and content capped at 2000 chars.
        tags = await self._generate_tags(content, entity_name)

        tag_line = " ".join(f"#{t}" for t in tags)
        structured_markdown = (
            f"# Entity: {entity_name}\n"
            f"## Source: {filename}\n"
            f"### Extracted: {timestamp}\n"
            f"### Confidence: {confidence:.2f}\n"
            f"### Chunk ID: {chunk_id}\n\n"
            f"{content}\n\n"
            f"### Related Chunks\n"
            f"- [[source-file:{filename}]]\n\n"
            f"### Tags\n"
            f"- {tag_line}\n"
        )

        return {
            "chunk_id": chunk_id,
            "filename": filename,
            "filepath": filepath,
            "raw_content": content,
            "markdown": structured_markdown,
            "confidence": round(confidence, 2),
            "timestamp": timestamp,
            "is_image": is_image,
            "parse_error": parse_error,
            "tags": tags,
        }

    @staticmethod
    def _extract_inline_tags(markdown: str) -> List[str]:
        """Extract #tags from markdown text. Word-boundary aware so C# / F# are ignored.

        Returns deduped tags (lowercase), preserving first-seen order.
        Used both internally for parsing the LLM tag response and exported for
        the orchestrator + tests.
        """
        if not markdown:
            return []
        # Hash must be preceded by start-of-string or whitespace (avoids C# / F# / #5)
        found = re.findall(r"(?:^|\s)#([a-z0-9][a-z0-9_-]{1,30})", markdown.lower())
        seen: set = set()
        unique: List[str] = []
        for t in found:
            if t not in seen:
                seen.add(t)
                unique.append(t)
            if len(unique) >= 8:
                break
        return unique

    def _fallback_parse(self, filepath: str) -> Tuple[str, Optional[str]]:
        """
        Fallback simple parser for TXT/MD and generic binary text extraction.
        Returns (content, error). error is None on success, str on failure.
        """
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(), None
        except Exception as e:
            return f"[Parsing Error: Could not read file content. {e}]", str(e)

    async def _generate_tags(self, content: str, entity_name: str) -> List[str]:
        """Auto-generate 3-5 #tags for the chunk using a cheap LLM.

        Cost discipline:
        - Single LLM call per chunk
        - Content capped at 2000 chars (truncate from middle, keep start+end)
        - Uses the cheap nemotron vision model (handles text too)
        - Falls back to ['untagged'] on any failure (no gateway, error, empty
          content, malformed output) — never raises

        Tag rules:
        - Lowercase, alphanumeric + dash/underscore
        - Dedupe and cap at 5 tags per chunk
        - Prefer the fixed taxonomy (TAG_TAXONOMY) but allow the model to
          invent new ones when nothing fits (e.g. #cat, #invoice)
        """
        if not content or not content.strip():
            return ["untagged"]
        if not self.gateway:
            logger.debug("No gateway for tag generation; using 'untagged' fallback.")
            return ["untagged"]

        # Truncate content intelligently — keep start + end so context is preserved
        MAX_CONTENT_CHARS = 2000
        if len(content) > MAX_CONTENT_CHARS:
            half = MAX_CONTENT_CHARS // 2
            content_for_llm = content[:half] + "\n\n[...truncated...]\n\n" + content[-half:]
        else:
            content_for_llm = content

        prompt = (
            f"Read this content about the entity '{entity_name}'. "
            f"Produce 3-5 hashtags that describe what this content is about.\n\n"
            f"Preferred tags (use when relevant): {self.TAG_TAXONOMY}\n\n"
            f"You may invent new tags if none of those fit (lowercase, alphanumeric, "
            f"one word or hyphenated — e.g. #cat, #invoice, #q3-report).\n\n"
            f"Reply with ONLY the hashtags, space-separated, nothing else. "
            f"Example response: #health #vet #cat #diet\n\n"
            f"Content:\n{content_for_llm}"
        )

        try:
            resp = await self.gateway.chat(
                self.tag_model,
                [{"role": "user", "content": prompt}],
            )
            raw = (resp.get("content") or "").strip()
            unique = self._extract_inline_tags(raw)
            if not unique:
                logger.warning(f"Tag LLM returned no parseable hashtags for {entity_name}: {raw[:80]!r}")
                return ["untagged"]
            # Cap at 5 for chunks (orchestrator/wiki body caps at 8)
            if len(unique) > 5:
                unique = unique[:5]
            logger.info(f"Generated tags for {entity_name}: {unique}")
            return unique
        except Exception as e:
            logger.warning(f"Tag generation failed for {entity_name}: {e}")
            return ["untagged"]

    async def _parse_image_vision(self, filepath: str, entity_name: str) -> tuple[str, float]:
        """
        Dual-pass image intelligence logic:
        Pass 1: Cheap vision model check (Gemini 2.5 Flash or Qwen-VL).
        Pass 2: If vital information is detected, escalate to premium model (Claude 3.5 Sonnet / GPT-4o).
        """
        if not self.gateway:
            logger.warning("No AI gateway configured. Vision parsing fell back to basic OCR note.")
            return f"[Image uploaded: {os.path.basename(filepath)}. AI Gateway not available for OCR.]", 0.1

        # Pass 1: Cheap vision check
        prompt_pass1 = (
            f"You are looking at an image uploaded for the entity '{entity_name}'. "
            f"First, describe what you see in the image and extract any visible text. "
            f"Second, end your response with EXACTLY 'VITAL_INFO: TRUE' or 'VITAL_INFO: FALSE' "
            f"indicating whether this image holds critical, high-value, or sensitive information "
            f"that requires deep analysis (e.g. contracts, medical data, evidence, maps, detailed charts)."
        )

        logger.info(f"Vision Pass 1: Cheap evaluation for {os.path.basename(filepath)}")
        
        # Use a fast cheap model, e.g. gemini-2.0-flash-exp or nvidia/nemotron-nano-12b-v2-vl:free
        cheap_model = "openrouter/nvidia/nemotron-nano-12b-v2-vl:free"
        messages = [
            {"role": "user", "content": prompt_pass1}
        ]
        
        response1 = await self.gateway.chat(cheap_model, messages)
        content1 = response1.get("content", "")
        
        # Determine if vital
        is_vital = "VITAL_INFO: TRUE" in content1 or "vital_info: true" in content1.lower()
        
        if is_vital:
            logger.info(f"Vision Pass 2: Escalating to premium model for vital content in {os.path.basename(filepath)}")
            premium_model = "openrouter/anthropic/claude-3.5-sonnet"
            prompt_pass2 = (
                f"This image was flagged as containing vital information for helping the entity '{entity_name}'. "
                f"Analyze it thoroughly. Extract all textual content verbatim, describe structural details, "
                f"interpret any charts/diagrams, and analyze the implications for helping the entity."
            )
            messages_pass2 = [
                {"role": "user", "content": prompt_pass2}
            ]
            response2 = await self.gateway.chat(premium_model, messages_pass2)
            content2 = response2.get("content", "")
            return content2, 0.95
        
        return content1, 0.75
