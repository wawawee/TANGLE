#!/bin/bash
# scripts/init-team.sh

PROJECT_ROOT="/Users/perbrinell/Documents/SAMI"
TEAM_ROOT="$PROJECT_ROOT/twisted-stacks-agentic-team"

echo "🚀 Initializing Twisted Stacks Agentic Team structure in $TEAM_ROOT..."

# Create core directory structure
mkdir -p "$TEAM_ROOT"/{system,memory/{global/{PLAYBOOKS,DECISIONS},logs/{archive},agents},contexts/{active,archive},skills,qdrant/{collections,schemas,sync}}

# Create agent-specific folders
for i in {01..13}; do
    mkdir -p "$TEAM_ROOT/memory/agents/agent-$(printf "%02d" $i)"
done

# Create placeholder system files
touch "$TEAM_ROOT/system/"{AGENTS,ORCHESTRATOR,QDRANT_CONFIG,SYSTEM_PROMPTS}.md
touch "$TEAM_ROOT/memory/global/"{MEMORY,SOUL}.md
touch "$TEAM_ROOT/qdrant/collections/"{memories,skills,contexts,conversations}.yaml

echo "✨ Structure initialized successfully!"
