#!/bin/bash

REPO="vercel/next.js"  # Replace with a known repo
TOKEN="$GITHUB_TOKEN"
OUTDIR="ideas/queue"
mkdir -p "$OUTDIR"

echo ">> Using token: ${TOKEN:0:5}... (short preview only)"
echo ">> Repo: $REPO"

echo ">> Fetching issues from GitHub..."

response=$(curl -s -H "Accept: application/vnd.github+json" \
    -H "Authorization: token $TOKEN" \
    "https://api.github.com/search/issues?q=repo:$REPO+is:issue+is:open")

# Save raw output for debugging
echo "$response" > debug_raw.json

echo "$response" | jq -c '.items[]' | while read -r issue; do
    ID=$(echo "$issue" | jq -r '.id')
    echo "$issue" > "$OUTDIR/$ID.json"
    echo "✅ Queued issue $ID"
done

