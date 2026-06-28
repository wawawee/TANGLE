-- TANGLE local Supabase migration
-- Run once via:  supabase db execute --db-url postgresql://postgres:postgres@127.0.0.1:54422/postgres -f supabase/migrations/00000000000001_tangle_initial.sql
--
-- Created 2026-06-29 when switching TANGLE from cloud Supabase (gxvtugvppnetycluwiya)
-- to local Docker Supabase (port 54421-54424, project_id DROPHELP).

-- pgvector extension (required for embedding column type)
CREATE EXTENSION IF NOT EXISTS vector;

-- wiki_entries — mirrors SQLite source of truth
CREATE TABLE IF NOT EXISTS wiki_entries (
    chunk_id    TEXT PRIMARY KEY,
    entity_name TEXT NOT NULL,
    filename    TEXT,
    filepath    TEXT,
    raw_content TEXT,
    markdown    TEXT,
    confidence  REAL,
    "timestamp" TEXT
);

-- missions — synthesized reports
CREATE TABLE IF NOT EXISTS missions (
    mission_id TEXT PRIMARY KEY,
    entity_name TEXT,
    status     TEXT,
    report     TEXT,
    "timestamp" TEXT
);

-- pgvector embedding column (4096-dim to match local qwen3-embedding:8b)
-- If migrating from old 1536-dim cloud schema: drop column first then add.
ALTER TABLE wiki_entries ADD COLUMN IF NOT EXISTS embedding vector(4096);

-- Search RPC function called by vector_store._search_wiki_supabase()
CREATE OR REPLACE FUNCTION search_wiki_entries(
    query_embedding vector(4096),
    match_entity    text,
    match_limit     int DEFAULT 5
) RETURNS TABLE(
    chunk_id     text,
    entity_name  text,
    filename     text,
    filepath     text,
    raw_content  text,
    markdown     text,
    confidence   real,
    "timestamp"    text,
    similarity   float
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        we.chunk_id,
        we.entity_name,
        we.filename,
        we.filepath,
        we.raw_content,
        we.markdown,
        we.confidence,
        we."timestamp",
        1 - (we.embedding <=> query_embedding) AS similarity
    FROM wiki_entries we
    WHERE we.entity_name = match_entity
    ORDER BY we.embedding <=> query_embedding
    LIMIT match_limit;
END;
$$;
