#!/bin/bash
# === pull_and_run.sh ===
# Updates codebase, runs current swarm task, and updates status

REPO_DIR="$HOME/One_at_a_Time_Machine"
cd "$REPO_DIR" || exit 1

# Step 1: Pull latest changes from GitHub
echo "🔄 Pulling latest updates from GitHub..."
git pull --rebase

# Step 2: Load current state
STATE_FILE="machine_state.json"
if [ ! -f "$STATE_FILE" ]; then
  echo "❌ machine_state.json not found!"
  exit 1
fi

ACTIVE_ID=$(jq -r .active_issue_id $STATE_FILE)
STAGE=$(jq -r .current_stage $STATE_FILE)
NODE_ID=$(jq -r .node_id $STATE_FILE)

# Step 3: Take action based on stage
case $STAGE in
  discovery)
    echo "🔍 Running discovery phase..."
    bash scripts/discover.sh
    ;;

  scoring)
    echo "📊 Scoring and queuing..."
    python3 scripts/score_and_queue.py
    ;;

  prompt_pending)
    echo "🧠 Generating prompt from active issue..."
    python3 scripts/process_active.py
    ;;

  spec_pending)
    echo "📥 Waiting for manual spec.md input..."
    echo "⚠️  Paste Claude/GPT output to ideas/active/spec.md manually."
    ;;

  repo_ready)
    echo "🚀 Creating repo from spec..."
    python3 scripts/create_repo_and_push.py
    ;;

  *)
    echo "⚠️  Unknown or idle stage: $STAGE. No action taken."
    ;;
esac

# Step 4: Update state timestamp and regenerate status
python3 scripts/update_state.py --stage "$STAGE" --node "$NODE_ID"
echo "✅ pull_and_run.sh completed."
exit 0
