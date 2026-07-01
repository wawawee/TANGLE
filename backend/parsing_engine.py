"""Universal file ingestion & parsing engine for TANGLE"""

import os
import re
import uuid
import base64
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Tuple, List

logger = logging.getLogger("tangle.parser")

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

try:
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    MARKER_AVAILABLE = True
except Exception as e:
    MARKER_AVAILABLE = False
    logger.warning(f"Marker PDF converter not available: {e}")

try:
    from chonkie import SemanticChunker
    CHONKIE_AVAILABLE = True
except Exception as e:
    CHONKIE_AVAILABLE = False
    logger.warning(f"Chonkie semantic chunker not available: {e}")

AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".webm")
PDF_EXTENSIONS = (".pdf",)

class ParsingEngine:
    def __init__(self, gateway=None):
        self.gateway = gateway
        self.mid = MarkItDown() if MARKITDOWN_AVAILABLE else None
        self.tag_model = "openrouter/nvidia/nemotron-nano-12b-v2-vl:free"
        self._marker_converter = None
        self._chunker = None
        self._event_callbacks: list = []

    def _emit_event(self, event_type: str, data: dict):
        import time
        for cb in self._event_callbacks:
            try:
                cb({"type": event_type, "payload": data, "ts": time.time()})
            except Exception as e:
                logger.warning(f"Event callback error: {e}")

    def on_event(self, cb):
        self._event_callbacks.append(cb)

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
        is_audio = ext in AUDIO_EXTENSIONS

        if is_audio:
            content, confidence = await self._transcribe_audio(filepath, entity_name)
        elif is_image:
            content, confidence = await self._parse_image_vision(filepath, entity_name)
        elif ext in PDF_EXTENSIONS and MARKER_AVAILABLE:
            marker_content, marker_err = await self._parse_with_marker(filepath)
            if marker_content:
                content = marker_content
                confidence = 0.95
            else:
                logger.warning(f"Marker failed for {filename}, trying fallback: {marker_err}")
                content, parse_error = self._fallback_parse(filepath)
                confidence = 0.5
        elif MARKITDOWN_AVAILABLE and self.mid:
            try:
                result = self.mid.convert(filepath)
                content = result.text_content
            except Exception as e:
                logger.error(f"MarkItDown conversion failed for {filename}: {e}")
                content, parse_error = self._fallback_parse(filepath)
                confidence = 0.5
        else:
            content, parse_error = self._fallback_parse(filepath)
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

        chunks = self.chunk_content(content, filename)

        return {
            "chunk_id": chunk_id,
            "filename": filename,
            "filepath": filepath,
            "raw_content": content,
            "markdown": structured_markdown,
            "confidence": round(confidence, 2),
            "timestamp": timestamp,
            "is_image": is_image,
            "is_audio": is_audio,
            "parse_error": parse_error,
            "tags": tags,
            "semantic_chunks": chunks,
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

    async def _parse_with_marker(self, filepath: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse a PDF using Marker (deep-learning PDF→markdown)."""
        filename = os.path.basename(filepath)
        logger.info(f"Marker parsing: {filename}")
        try:
            if not self._marker_converter:
                self._marker_converter = PdfConverter(
                    artifact_dict=create_model_dict(),
                )
            rendered = self._marker_converter(filepath)
            text, _, images = text_from_rendered(rendered)
            return text, None
        except Exception as e:
            logger.error(f"Marker error for {filename}: {e}", exc_info=True)
            return None, str(e)

    def chunk_content(self, content: str, filename: str, chunk_size: int = 1500) -> List[Dict[str, Any]]:
        """Split content into semantic chunks using Chonkie. Falls back to naive split."""
        if not content:
            return [{"text": "", "start": 0, "end": 0}]

        if CHONKIE_AVAILABLE:
            try:
                if not self._chunker:
                    self._chunker = SemanticChunker(max_chunk_size=chunk_size)
                chunks = self._chunker.chunk(content)
                if chunks:
                    return [{"text": c.text, "start": c.start_idx, "end": c.end_idx} for c in chunks]
            except Exception as e:
                logger.warning(f"Chonkie chunking failed for {filename}: {e}")

        words = content.split()
        chunked = []
        for i in range(0, len(words), chunk_size):
            segment = " ".join(words[i:i + chunk_size])
            chunked.append({"text": segment, "start": i, "end": i + len(segment.split())})
        return chunked

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

    async def _transcribe_audio(self, filepath: str, entity_name: str) -> tuple[str, float]:
        """
        Transcribe audio — local mlx-whisper (default) or OpenRouter Whisper fallback.
        Controlled by TANGLE_AUDIO_SOURCE env var ('local' or 'openrouter').
        """
        source = os.environ.get("TANGLE_AUDIO_SOURCE", "local")

        if source == "local":
            return await self._transcribe_local(filepath)

        return await self._transcribe_openrouter(filepath)

    async def _transcribe_local(self, filepath: str) -> tuple[str, float]:
        """Local mlx-whisper with GPU limiting, chunking, and progress events."""
        from audio_transcriber import transcribe, estimate, get_duration

        duration_s = get_duration(filepath)
        est = estimate(duration_s)

        if est["warning"]:
            msg = est["warning_message"]
            logger.warning(msg)
            self._emit_event("transcription_warning", {
                "message": msg,
                "duration_hours": est["duration_hours"],
                "estimated_minutes": est["estimated_transcription_min"],
                "chunks": est["chunks"],
            })

        self._emit_event("transcription_start", {
            "duration_s": duration_s,
            "estimated_minutes": est["estimated_transcription_min"],
            "chunks": est["chunks"],
        })

        import asyncio
        loop = asyncio.get_event_loop()

        def _run():
            safe_emit = lambda done, total, eta: loop.call_soon_threadsafe(
                self._emit_event, "transcription_progress", {
                    "chunk": done,
                    "total_chunks": total,
                    "progress_pct": round(done / total * 100, 1) if total > 0 else 0,
                    "eta_s": round(eta),
                    "eta_formatted": f"{int(eta // 60)}m {int(eta % 60)}s" if eta > 0 else "done",
                },
            )
            return transcribe(filepath, on_progress=safe_emit)

        result = await loop.run_in_executor(None, _run)

        self._emit_event("transcription_done", {
            "text_len": len(result.get("text", "")),
            "chunks": result["chunks"],
            "elapsed_s": result["elapsed_s"],
            "language": result["language"],
        })

        logger.info(f"Local transcription: {result['elapsed_s']}s for {result['chunks']} chunks")
        return result["text"].strip(), 0.90

    async def _transcribe_openrouter(self, filepath: str) -> tuple[str, float]:
        """
        Transcribe audio via OpenRouter Whisper.
        Calls POST /api/v1/audio/transcriptions with the audio file.
        Falls back to a simple message on failure.
        """
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return (
                f"[Audio uploaded: {os.path.basename(filepath)}. "
                "OPENROUTER_API_KEY not configured for transcription.]",
                0.1
            )

        import httpx

        filename = os.path.basename(filepath)
        _, ext = os.path.splitext(filename)
        mime_map = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".ogg": "audio/ogg",
            ".flac": "audio/flac",
            ".aac": "audio/aac",
            ".webm": "audio/webm",
        }
        mime = mime_map.get(ext, "audio/mpeg")

        logger.info(f"Transcribing audio: {filename} via OpenRouter Whisper")

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                with open(filepath, "rb") as f:
                    files = {
                        "model": (None, "openai/whisper-1"),
                        "file": (filename, f, mime),
                    }
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files=files,
                    )
                if resp.is_success:
                    data = resp.json()
                    text = data.get("text", "") or data.get("content", "")
                    logger.info(f"Transcription success for {filename}: {len(text)} chars")
                    return text.strip(), 0.85
                else:
                    logger.error(f"Transcription failed ({resp.status_code}): {resp.text[:200]}")
                    return (
                        f"[Audio file: {filename}. Transcription failed "
                        f"(HTTP {resp.status_code}).]",
                        0.2
                    )
        except Exception as e:
            logger.error(f"Transcription error for {filename}: {e}")
            return (
                f"[Audio file: {filename}. Transcription error: {e}]",
                0.1
            )

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
