"""Local audio transcription via mlx-whisper with GPU limiting, chunking, and progress."""

import os
import re
import json
import time
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Callable, Optional

import mlx.core as mx
import mlx_whisper

logger = logging.getLogger("tangle.audio")

DEFAULT_GPU_MEMORY_LIMIT = 4 * 1024 ** 3  # 4 GB — leaves room for other processes
DEFAULT_CHUNK_S = 300  # 5 minutes per chunk
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".aac", ".webm"}


def get_duration(filepath: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", filepath],
        capture_output=True, text=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def _split(filepath: str, chunk_s: int = DEFAULT_CHUNK_S) -> list[tuple[str, float, float]]:
    duration = get_duration(filepath)
    tmp = tempfile.mkdtemp()
    chunks = []
    for i, start in enumerate(range(0, int(duration), chunk_s)):
        end = min(start + chunk_s, duration)
        out = os.path.join(tmp, f"chunk_{i:04d}.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-i", filepath,
             "-ss", str(start), "-to", str(end),
             "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", out],
            capture_output=True, check=True,
        )
        chunks.append((out, start, end))
    return chunks


def estimate(duration_s: float) -> dict:
    estimated_s = duration_s / 100
    hours = duration_s / 3600
    return {
        "duration_s": duration_s,
        "duration_hours": round(hours, 1),
        "estimated_transcription_s": round(estimated_s),
        "estimated_transcription_min": round(estimated_s / 60, 1),
        "chunks": max(1, int(duration_s / DEFAULT_CHUNK_S)),
        "warning": hours > 0.5,
        "warning_message": (
            f"This audio is {hours:.1f}h long. "
            f"Estimated transcription time: ~{estimated_s/60:.0f} minutes. "
            f"The file will be split into {max(1, int(duration_s / DEFAULT_CHUNK_S))} chunks."
        ),
    }


def transcribe(
    filepath: str,
    model: str = WHISPER_MODEL,
    chunk_s: int = DEFAULT_CHUNK_S,
    gpu_limit: int = DEFAULT_GPU_MEMORY_LIMIT,
    verbose: bool = False,
    on_progress: Optional[Callable] = None,
) -> dict:
    """Transcribe audio with mlx-whisper. GPU-limited, chunked, progress callback."""
    mx.metal.set_memory_limit(gpu_limit)
    logger.info(f"GPU memory limited to {gpu_limit / 1024**3:.1f} GB")

    duration = get_duration(filepath)
    logger.info(f"Audio duration: {duration:.0f}s")

    if duration <= chunk_s:
        start = time.time()
        result = mlx_whisper.transcribe(
            filepath, path_or_hf_repo=model,
            verbose=verbose, word_timestamps=True,
        )
        elapsed = time.time() - start
        if on_progress:
            on_progress(1, 1, 0)
        return _fmt(result, filepath, duration, elapsed)

    chunks = _split(filepath, chunk_s)
    total = len(chunks)
    all_segments = []
    total_start = time.time()

    logger.info(f"Split into {total} chunks of {chunk_s}s each")

    for i, (chunk_path, start_sec, end_sec) in enumerate(chunks):
        logger.info(f"Chunk {i + 1}/{total} ({start_sec:.0f}s–{end_sec:.0f}s)")
        if on_progress:
            if i > 0:
                avg = (time.time() - total_start) / i
                remaining = avg * (total - i)
            else:
                remaining = (duration / chunk_s) * (end_sec - start_sec) * 2
            on_progress(i, total, remaining)

        result = mlx_whisper.transcribe(
            chunk_path, path_or_hf_repo=model,
            verbose=verbose, word_timestamps=True,
        )
        for seg in result.get("segments", []):
            seg["start"] += start_sec
            seg["end"] += start_sec
            if "words" in seg:
                for w in seg["words"]:
                    w["start"] += start_sec
                    w["end"] += start_sec
            all_segments.append(seg)
        try:
            os.remove(chunk_path)
        except OSError:
            pass

    try:
        os.rmdir(Path(chunks[0][0]).parent)
    except OSError:
        pass

    total_elapsed = time.time() - total_start
    if on_progress:
        on_progress(total, total, 0)

    return {
        "text": " ".join(s["text"] for s in all_segments),
        "segments": all_segments,
        "duration_s": duration,
        "chunks": total,
        "elapsed_s": round(total_elapsed, 2),
        "model": model,
        "language": result.get("language", "unknown"),
    }


def _fmt(result: dict, filepath: str, duration_s: float, elapsed_s: float) -> dict:
    return {
        "text": result.get("text", ""),
        "segments": result.get("segments", []),
        "duration_s": duration_s,
        "chunks": 1,
        "elapsed_s": round(elapsed_s, 2),
        "model": result.get("model", WHISPER_MODEL),
        "language": result.get("language", "unknown"),
    }
