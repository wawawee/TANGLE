"""Vector store & metadata DB integration layer for TANGLE"""

import os
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger("tangle.vector")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    logger.warning("qdrant-client not installed. Using in-memory fallback vector search.")

# ── Supabase toggle ─────────────────────────────────────────
SUPABASE_ENABLED = os.getenv("TANGLE_SUPABASE_ENABLED", "").strip() in ("1", "true", "True")
SUPABASE_AVAILABLE = False
_supabase_client = None
if SUPABASE_ENABLED:
    try:
        from supabase import create_client, Client
        _supabase_url = os.getenv("SUPABASE_URL", "")
        _supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
        if _supabase_url and _supabase_key:
            _supabase_client = create_client(_supabase_url, _supabase_key)
            SUPABASE_AVAILABLE = True
            logger.info(f"Supabase client initialized for {_supabase_url}")
        else:
            logger.warning(
                "TANGLE_SUPABASE_ENABLED=1 but SUPABASE_URL or SUPABASE_ANON_KEY not set. "
                "Supabase mirroring disabled."
            )
    except ImportError:
        logger.warning(
            "TANGLE_SUPABASE_ENABLED=1 but supabase-py not installed. "
            "Install: pip install supabase"
        )
    except Exception as e:
        logger.warning(f"Supabase client init failed: {e}. Supabase mirroring disabled.")

class VectorStore:
    def __init__(self):
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_key = os.getenv("QDRANT_API_KEY", "")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        
        self.db_path = os.path.join(os.path.dirname(__file__), "tangle.db")
        self._init_sqlite()
        
        self.qclient = None
        if QDRANT_AVAILABLE:
            try:
                if self.qdrant_key:
                    self.qclient = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_key, timeout=10)
                else:
                    self.qclient = QdrantClient(url=self.qdrant_url, timeout=10)
                logger.info(f"Connected to Qdrant at {self.qdrant_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Qdrant: {e}")
                self.qclient = None

        # Fallback in-memory store for vectors
        self.memory_vectors = []
        self.supabase = _supabase_client if SUPABASE_AVAILABLE else None
        if self.supabase:
            self._init_supabase()

    def _init_sqlite(self):
        """Initializes the local fallback SQLite database for relational state/wiki metadata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for files & chunks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wiki_entries (
                chunk_id TEXT PRIMARY KEY,
                entity_name TEXT,
                filename TEXT,
                filepath TEXT,
                raw_content TEXT,
                markdown TEXT,
                confidence REAL,
                timestamp TEXT
            )
        """)
        
        # Table for synthesized reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                mission_id TEXT PRIMARY KEY,
                entity_name TEXT,
                status TEXT,
                report TEXT,
                timestamp TEXT
            )
        """)
        
        conn.commit()
        conn.close()

    def _init_supabase(self):
        """Ensure Supabase tables exist (wiki_entries + missions).

        Best-effort: tries RPC exec_sql first, falls back to probing
        the tables. If tables don't exist, logs a warning with manual
        SQL — writes will be skipped until tables are created.
        """
        if not self.supabase:
            return
        ddl = (
            "CREATE TABLE IF NOT EXISTS wiki_entries ("
            "chunk_id TEXT PRIMARY KEY, entity_name TEXT, filename TEXT, "
            "filepath TEXT, raw_content TEXT, markdown TEXT, "
            "confidence REAL, timestamp TEXT"
            ");"
            "CREATE TABLE IF NOT EXISTS missions ("
            "mission_id TEXT PRIMARY KEY, entity_name TEXT, "
            "status TEXT, report TEXT, timestamp TEXT"
            ");"
            # pgvector column — added 2026-06-28 for Supabase vector search fallback.
            # The extension (CREATE EXTENSION IF NOT EXISTS vector) and index
            # must be created manually in Supabase SQL Editor (see .env.example).
            # If the column doesn't exist yet, ALTER TABLE ADD COLUMN IF NOT EXISTS
            # is idempotent and won't break the table probe.
            "ALTER TABLE wiki_entries ADD COLUMN IF NOT EXISTS embedding vector(1536);"
            # Search RPC function — called by _search_wiki_supabase() for
            # pgvector cosine similarity search. Must exist for pgvector fallback.
            "CREATE OR REPLACE FUNCTION search_wiki_entries("
            "query_embedding vector(1536), match_entity text, match_limit int DEFAULT 5"
            ") RETURNS TABLE(chunk_id text, entity_name text, filename text, "
            "filepath text, raw_content text, markdown text, confidence real, "
            "timestamp text, similarity float) LANGUAGE plpgsql AS $$ "
            "BEGIN RETURN QUERY SELECT we.chunk_id, we.entity_name, we.filename, "
            "we.filepath, we.raw_content, we.markdown, we.confidence, we.timestamp, "
            "1 - (we.embedding <=> query_embedding) AS similarity "
            "FROM wiki_entries we WHERE we.entity_name = match_entity "
            "ORDER BY we.embedding <=> query_embedding LIMIT match_limit; END; $$;"
        )
        try:
            self.supabase.rpc("exec_sql", {"sql": ddl}).execute()
            logger.info("Supabase wiki_entries table initialized")
        except Exception:
            try:
                self.supabase.table("wiki_entries").select("chunk_id", count="exact").limit(0).execute()
                logger.info("Supabase wiki_entries table already exists")
            except Exception as e:
                logger.warning(
                    f"Supabase table init failed: {e}. "
                    f"Create wiki_entries + missions tables manually in Supabase SQL Editor. "
                    f"Writes will be skipped until tables exist."
                )

    async def get_embeddings(self, text: str) -> List[float]:
        """Generates embedding vector for text using OpenRouter or fallback"""
        if not self.openrouter_key:
            return self._generate_dummy_vector(text)

        try:
            # We can use text-embedding-3-small via OpenRouter
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.openrouter_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "openai/text-embedding-3-small",
                        "input": text
                    },
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data["data"][0]["embedding"]
                else:
                    logger.error(f"OpenRouter embedding error: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            
        return self._generate_dummy_vector(text)

    def _generate_dummy_vector(self, text: str, dimensions: int = 1536) -> List[float]:
        """Generates a pseudo-deterministic vector based on text hashing for offline fallback"""
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(dimensions):
            val = (h[i % 32] * (i + 1)) % 1000
            vector.append(val / 1000.0)
        return vector

    async def add_wiki_entry(self, parsed_data: Dict[str, Any], entity_name: str):
        """Saves wiki entry to database and vector database"""
        chunk_id = parsed_data["chunk_id"]
        filename = parsed_data["filename"]
        filepath = parsed_data["filepath"]
        raw_content = parsed_data["raw_content"]
        markdown = parsed_data["markdown"]
        confidence = parsed_data["confidence"]
        timestamp = parsed_data["timestamp"]

        # 1. Save to Relational DB (SQLite — source of truth)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO wiki_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, entity_name, filename, filepath, raw_content, markdown, confidence, timestamp)
        )
        conn.commit()
        conn.close()

        # 1b. Mirror to Supabase (best-effort, non-blocking)
        if self.supabase:
            try:
                row = {
                    "chunk_id": chunk_id,
                    "entity_name": entity_name,
                    "filename": filename,
                    "filepath": filepath,
                    "raw_content": raw_content,
                    "markdown": markdown,
                    "confidence": confidence,
                    "timestamp": timestamp,
                }
                self.supabase.table("wiki_entries").upsert(row).execute()
            except Exception as e:
                logger.warning(f"Supabase wiki_entry mirror failed for {chunk_id}: {e}")

        # 2. Get embeddings
        vector = await self.get_embeddings(raw_content)

        # 2b. Store embedding in Supabase for pgvector search (best-effort)
        if self.supabase:
            try:
                self.supabase.table("wiki_entries").update(
                    {"embedding": vector}
                ).eq("chunk_id", chunk_id).execute()
            except Exception as e:
                logger.debug(f"Supabase embedding store skipped for {chunk_id}: {e}")

        # 3. Save to Vector Store (Qdrant)
        collection_name = "tangle_wiki_memories"
        if self.qclient:
            try:
                # Ensure collection exists
                collections = self.qclient.get_collections().collections
                exists = any(c.name == collection_name for c in collections)
                if not exists:
                    self.qclient.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(size=len(vector), distance=Distance.COSINE)
                    )
                
                # Upsert point
                self.qclient.upsert(
                    collection_name=collection_name,
                    points=[
                        PointStruct(
                            id=hash(chunk_id) % (10**15),  # Convert UUID hash to int
                            vector=vector,
                            payload={
                                "chunk_id": chunk_id,
                                "entity_name": entity_name,
                                "filename": filename,
                                "content": raw_content[:1000]
                            }
                        )
                    ]
                )
                logger.info(f"Upserted vector into Qdrant for {chunk_id}")
            except Exception as e:
                logger.error(f"Qdrant upsert failed: {e}. Falling back to memory.")
                self.memory_vectors.append({"vector": vector, "payload": {"chunk_id": chunk_id, "entity_name": entity_name, "content": raw_content}})
        else:
            self.memory_vectors.append({"vector": vector, "payload": {"chunk_id": chunk_id, "entity_name": entity_name, "content": raw_content}})

    async def _search_wiki_supabase(self, vector: List[float], entity_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Supabase via pgvector cosine similarity (RPC fallback).

        Requires the search_wiki_entries RPC function to exist in Supabase
        (created by _init_supabase DDL or manually). Returns empty list on
        any failure — caller falls back to SQLite keywords.
        """
        if not self.supabase:
            return []
        try:
            resp = self.supabase.rpc(
                "search_wiki_entries",
                {
                    "query_embedding": vector,
                    "match_entity": entity_name,
                    "match_limit": limit,
                },
            ).execute()
            rows = resp.data or []
            results: List[Dict[str, Any]] = []
            for row in rows:
                results.append({
                    "chunk_id": row.get("chunk_id", ""),
                    "entity_name": row.get("entity_name", entity_name),
                    "filename": row.get("filename", ""),
                    "filepath": row.get("filepath", ""),
                    "raw_content": row.get("raw_content", ""),
                    "markdown": row.get("markdown", ""),
                    "confidence": row.get("confidence", 0.0),
                    "timestamp": row.get("timestamp", ""),
                })
            if results:
                logger.info(f"Supabase pgvector search found {len(results)} results for {entity_name}")
            return results
        except Exception as e:
            logger.warning(f"Supabase pgvector search failed: {e}")
            return []

    async def search_wiki(self, query: str, entity_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches vector DB for chunks matching the query for a specific entity"""
        vector = await self.get_embeddings(query)
        collection_name = "tangle_wiki_memories"
        results = []

        if self.qclient:
            try:
                search_results = self.qclient.search(
                    collection_name=collection_name,
                    query_vector=vector,
                    query_filter={
                        "must": [
                            {"key": "entity_name", "match": {"value": entity_name}}
                        ]
                    },
                    limit=limit
                )
                
                chunk_ids = [r.payload["chunk_id"] for r in search_results]
                
                # Fetch full data from sqlite
                if chunk_ids:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    placeholders = ",".join("?" for _ in chunk_ids)
                    cursor.execute(f"SELECT * FROM wiki_entries WHERE chunk_id IN ({placeholders})", chunk_ids)
                    rows = cursor.fetchall()
                    conn.close()
                    
                    for row in rows:
                        results.append({
                            "chunk_id": row[0],
                            "entity_name": row[1],
                            "filename": row[2],
                            "filepath": row[3],
                            "raw_content": row[4],
                            "markdown": row[5],
                            "confidence": row[6],
                            "timestamp": row[7]
                        })
                return results
            except Exception as e:
                logger.error(f"Qdrant search failed: {e}. Trying Supabase pgvector.")

        # Supabase pgvector fallback (when Qdrant is down/unavailable)
        if self.supabase:
            results = await self._search_wiki_supabase(vector, entity_name, limit)
            if results:
                return results

        # SQLite Keyword fallback if Qdrant isn't working
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM wiki_entries WHERE entity_name = ? AND raw_content LIKE ? LIMIT ?",
            (entity_name, f"%{query}%", limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            results.append({
                "chunk_id": row[0],
                "entity_name": row[1],
                "filename": row[2],
                "filepath": row[3],
                "raw_content": row[4],
                "markdown": row[5],
                "confidence": row[6],
                "timestamp": row[7]
            })
        return results

    def save_mission(self, mission_id: str, entity_name: str, report: str, status: str = "completed"):
        """Saves a help mission synthesized report"""
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO missions VALUES (?, ?, ?, ?, ?)",
            (mission_id, entity_name, status, report, ts)
        )
        conn.commit()
        conn.close()

        # Mirror to Supabase (best-effort, non-blocking)
        if self.supabase:
            try:
                row = {
                    "mission_id": mission_id,
                    "entity_name": entity_name,
                    "status": status,
                    "report": report,
                    "timestamp": ts,
                }
                self.supabase.table("missions").upsert(row).execute()
            except Exception as e:
                logger.warning(f"Supabase mission mirror failed for {mission_id}: {e}")

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a help mission by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM missions WHERE mission_id = ?", (mission_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "mission_id": row[0],
                "entity_name": row[1],
                "status": row[2],
                "report": row[3],
                "timestamp": row[4]
            }
        return None

    def get_supabase_stats(self) -> Dict[str, Any]:
        """Return Supabase entry counts for the admin/index endpoint.

        Returns counts from Supabase for wiki_entries and missions.
        When Supabase is unavailable, returns zero counts with an error note.
        """
        stats: Dict[str, Any] = {
            "wiki_entries_count": 0,
            "missions_count": 0,
            "by_entity": {},
        }
        if not self.supabase:
            return stats
        try:
            wiki = self.supabase.table("wiki_entries").select("chunk_id,entity_name", count="exact").execute()
            stats["wiki_entries_count"] = wiki.count or 0
            if wiki.data:
                by_entity: Dict[str, int] = {}
                for row in wiki.data:
                    en = row.get("entity_name", "unknown")
                    by_entity[en] = by_entity.get(en, 0) + 1
                stats["by_entity"] = by_entity
            missions = self.supabase.table("missions").select("mission_id", count="exact").execute()
            stats["missions_count"] = missions.count or 0
        except Exception as e:
            stats["error"] = str(e)
        return stats

    @property
    def supabase_available(self) -> bool:
        return self.supabase is not None
