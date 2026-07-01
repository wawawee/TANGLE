#!/bin/bash
# Stop all Docker containers not needed by DROPHELP.
# Keeps:
#   - supabase_*_DROPHELP   (TANGLE database backend)
#   - MCP servers           (active AI assistant session)
set -e

KEEP_PATTERN="DROPHELP"

echo "=== DROPHELP + MCP (will keep) ==="
docker ps --format "{{.Names}}" | while read name; do
  labels=$(docker inspect "$name" --format '{{json .Config.Labels}}' 2>/dev/null)
  if echo "$name" | grep -q "$KEEP_PATTERN" || echo "$labels" | grep -qiE "mcp|modelcontextprotocol"; then
    echo "  ✓ Keeping: $name"
  fi
done | sort

echo
echo "=== Stopping non-DROPHELP containers ==="
docker ps --format "{{.Names}}" | while read name; do
  labels=$(docker inspect "$name" --format '{{json .Config.Labels}}' 2>/dev/null)
  if echo "$name" | grep -q "$KEEP_PATTERN" || echo "$labels" | grep -qiE "mcp|modelcontextprotocol"; then
    true  # skip
  else
    echo "  ✗ Stopping: $name"
    docker stop "$name" >/dev/null 2>&1 || true
  fi
done

echo
echo "=== Cleaning exited/stopped containers ==="
EXITED=$(docker ps -aq --filter "status=exited" --filter "status=created" 2>/dev/null | wc -l | tr -d ' ')
if [ "$EXITED" -gt 0 ]; then
  echo "  Removing $EXITED exited/created containers..."
  docker container prune -f >/dev/null 2>&1
  echo "  Done."
else
  echo "  No exited containers to clean."
fi

echo
echo "=== Remaining running ==="
docker ps --format "table {{.Names}}\t{{.Status}}"
