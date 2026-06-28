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

        # 1. Save to Relational DB (SQLite fallback, and optionally Supabase)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO wiki_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, entity_name, filename, filepath, raw_content, markdown, confidence, timestamp)
        )
        conn.commit()
        conn.close()

        # 2. Get embeddings
        vector = await self.get_embeddings(raw_content)

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
                logger.error(f"Qdrant search failed: {e}. Falling back to SQLite keywords.")
        
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO missions VALUES (?, ?, ?, ?, ?)",
            (mission_id, entity_name, status, report, datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
        )
        conn.commit()
        conn.close()

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
