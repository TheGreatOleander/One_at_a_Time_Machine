#!/bin/bash
# === save_response.sh ===
# Paste an LLM response into spec.md manually (or redirect a file)

ACTIVE_DIR="ideas/active"
SPEC_PATH="$ACTIVE_DIR/spec.md"

# Check if there's an active idea
ISSUE_JSON=$(ls $ACTIVE_DIR/*.json 2>/dev/null | head -n 1)
if [ -z "$ISSUE_JSON" ]; then
  echo "❌ No active idea found in $ACTIVE_DIR"
  exit 1
fi

# Prompt for input or read from file
if [ -z "$1" ]; then
  echo "📥 Paste the response from Claude/GPT below. Press Ctrl+D when done."
  cat > "$SPEC_PATH"
else
  cp "$1" "$SPEC_PATH"
fi

echo "✅ Saved response to $SPEC_PATH"
ls -lh "$SPEC_PATH"
