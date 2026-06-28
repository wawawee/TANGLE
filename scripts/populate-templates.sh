#!/bin/bash
# scripts/populate-templates.sh

TEAM_ROOT="/Users/perbrinell/Documents/SAMI/twisted-stacks-agentic-team"
TEMPLATE_SRC="$TEAM_ROOT/memory/agents/agent-01-research"

echo "📝 Populating templates for all agents..."

for i in {02..13}; do
    AGENT_DIR="$TEAM_ROOT/memory/agents/agent-$(printf "%02d" $i)"
    cp "$TEMPLATE_SRC/IDENTITY.md" "$AGENT_DIR/"
    cp "$TEMPLATE_SRC/WORKING.md" "$AGENT_DIR/"
    cp "$TEMPLATE_SRC/KNOWLEDGE.md" "$AGENT_DIR/"

    # Customize IDENTITY.md slightly with the ID
    sed -i '' "s/\[ID\]/$(printf "%02d" $i)/g" "$AGENT_DIR/IDENTITY.md"
    sed -i '' "s/\[ID\]/$(printf "%02d" $i)/g" "$AGENT_DIR/WORKING.md"
    sed -i '' "s/\[ID\]/$(printf "%02d" $i)/g" "$AGENT_DIR/KNOWLEDGE.md"
done

# Fix agent-01 itself
sed -i '' "s/\[ID\]/01/g" "$TEMPLATE_SRC/IDENTITY.md"
sed -i '' "s/\[ID\]/01/g" "$TEMPLATE_SRC/WORKING.md"
sed -i '' "s/\[ID\]/01/g" "$TEMPLATE_SRC/KNOWLEDGE.md"

echo "✅ All agent folders populated with templates!"
