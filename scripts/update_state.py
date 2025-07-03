#!/data/data/com.termux/files/usr/bin/python3

# === update_state.py ===
# Safely updates machine_state.json with new info

import json
import argparse
from pathlib import Path
from datetime import datetime

STATE_PATH = Path("machine_state.json")

# Load current state
if STATE_PATH.exists():
    with open(STATE_PATH) as f:
        state = json.load(f)
else:
    state = {}

# Parse CLI args
parser = argparse.ArgumentParser()
parser.add_argument("--id", help="Set active issue ID")
parser.add_argument("--stage", help="Set current processing stage")
parser.add_argument("--file", help="Set latest prompt or output file path")
parser.add_argument("--repo", help="Set GitHub repo URL")
parser.add_argument("--node", help="Set this device/node ID")
args = parser.parse_args()

# Update fields
if args.id:
    state["active_issue_id"] = args.id
if args.stage:
    state["current_stage"] = args.stage
if args.file:
    if args.file.endswith("prompt.md"):
        state["last_prompt_file"] = args.file
    elif args.file.endswith("spec.md"):
        state["last_response_file"] = args.file
if args.repo:
    state["last_repo_pushed"] = args.repo
if args.node:
    state["node_id"] = args.node

# Always update timestamp
state["updated_at"] = datetime.utcnow().isoformat() + "Z"

# Save
with open(STATE_PATH, "w") as f:
    json.dump(state, f, indent=2)

print("✅ machine_state.json updated:")
print(json.dumps(state, indent=2))
