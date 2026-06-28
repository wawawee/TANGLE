#!/bin/bash
# TANGLE backup script — pg_dump Supabase + cp SQLite + Qdrant snapshot.
# Safe to run manually or via launchd. Keeps last 7 backups.
#
# Usage: bash scripts/backup.sh
#
# Env overrides:
#   TANGLE_SUPABASE_DB_URL    default: postgresql://postgres:postgres@127.0.0.1:54422/postgres
#   TANGLE_REPO               default: /Users/perbrinell/Documents/DROPHELP
#   TANGLE_BACKUP_DIR         default: ~/backups/tangle
#   TANGLE_BACKUP_KEEP        default: 7

set -euo pipefail

# ── Config ───────────────────────────────────────────────────
SUPABASE_DB_URL="${TANGLE_SUPABASE_DB_URL:-postgresql://postgres:postgres@127.0.0.1:54422/postgres}"
REPO="${TANGLE_REPO:-$HOME/Documents/DROPHELP}"
BACKUP_DIR="${TANGLE_BACKUP_DIR:-$HOME/backups/tangle}"
KEEP="${TANGLE_BACKUP_KEEP:-7}"

STAMP="$(date +%Y-%m-%d-%H%M)"
OUT="$BACKUP_DIR/$STAMP"

# ── Preflight ────────────────────────────────────────────────
if [[ ! -d "$REPO/backend" ]]; then
  echo "ERROR: TANGLE repo not found at $REPO" >&2
  exit 1
fi

mkdir -p "$OUT"

# ── 1. pg_dump Supabase ──────────────────────────────────────
echo "→ pg_dump Supabase ..."
if ! command -v docker >/dev/null; then
  echo "  WARN: docker not available; skipping Supabase dump"
else
  # pg_dump via docker exec into the local container (avoids needing psql+network)
  if docker ps --format '{{.Names}}' | grep -q '^supabase_db_DROPHELP$'; then
    docker exec supabase_db_DROPHELP pg_dump -U postgres -d postgres --clean --if-exists > "$OUT/supabase.sql" 2>>"$OUT/backup.log"
    SIZE=$(wc -c < "$OUT/supabase.sql" 2>/dev/null || echo 0)
    echo "  ✓ supabase.sql ($SIZE bytes)"
  else
    echo "  WARN: container 'supabase_db_DROPHELP' not running; skipping Supabase dump"
  fi
fi

# ── 2. SQLite copy ───────────────────────────────────────────
echo "→ SQLite tangle.db ..."
if [[ -f "$REPO/backend/tangle.db" ]]; then
  cp "$REPO/backend/tangle.db" "$OUT/tangle.db"
  SIZE=$(wc -c < "$OUT/tangle.db")
  echo "  ✓ tangle.db ($SIZE bytes)"
else
  echo "  WARN: tangle.db not found at $REPO/backend; skipping"
fi

# ── 3. Qdrant snapshot (best-effort) ─────────────────────────
echo "→ Qdrant snapshot ..."
if curl -sf http://localhost:6333/healthz >/dev/null 2>&1; then
  SNAP=$(curl -s -X POST 'http://localhost:6333/collections/tangle_wiki_memories/snapshots' 2>/dev/null)
  NAME=$(echo "$SNAP" | python3 -c "import json,sys;print(json.load(sys.stdin).get('result',{}).get('snapshot_name','snapshot-$STAMP'))" 2>/dev/null || echo "snapshot-$STAMP")
  # Qdrant stores snapshots inside its volume, not on host by default.
  # We just record the snapshot name so the operator can fetch it manually if needed.
  echo "$NAME" > "$OUT/qdrant-snapshot-name.txt"
  echo "  ✓ Qdrant snapshot: $NAME (stored inside container volume)"
else
  echo "  WARN: Qdrant not reachable; skipping"
fi

# ── 4. Manifest ──────────────────────────────────────────────
cat > "$OUT/MANIFEST.txt" <<EOF
TANGLE backup
=============
When:      $STAMP
Repo:      $REPO
Components:
- supabase.sql          $(if [[ -f "$OUT/supabase.sql" ]]; then wc -c <"$OUT/supabase.sql" | tr -d ' '; fi) bytes
- tangle.db             $(if [[ -f "$OUT/tangle.db" ]]; then wc -c <"$OUT/tangle.db" | tr -d ' '; fi) bytes
- qdrant snapshot name  $(cat "$OUT/qdrant-snapshot-name.txt" 2>/dev/null || echo "n/a")

Restore (manual):
1. Stop TANGLE backend
2. supabase db reset   # reloads migrations
3. psql -f supabase.sql  # inside supabase_db_DROPHELP container
4. cp tangle.db $REPO/backend/tangle.db
5. Restart backend
6. Run scripts/reseed_embeddings.py to rebuild Qdrant if needed
EOF
echo "  ✓ MANIFEST.txt"

# ── 5. Prune old backups ─────────────────────────────────────
echo "→ Pruning old backups (keep=$KEEP) ..."
cd "$BACKUP_DIR"
ls -dt [0-9]*/ 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -rf "$old"
  echo "  pruned $old"
done

# ── Summary ──────────────────────────────────────────────────
TOTAL=$(du -sh "$OUT" 2>/dev/null | cut -f1)
echo "✓ Backup complete: $OUT ($TOTAL)"
