import os
import json
import shutil
from pathlib import Path

QUEUE_DIR = Path("ideas/queue")
ACTIVE_DIR = Path("ideas/active")
SCORED_LOG = Path("ideas/scored_log.txt")

def score_issue(issue_data):
    score = 0
    title = issue_data.get("title", "").lower()
    comments = issue_data.get("comments", 0)
    body = issue_data.get("body", "").lower()

    if comments > 5:
        score += 20
    if any(word in title for word in ["critical", "crash", "fail", "leak"]):
        score += 30
    if "reproduc" in body or "steps" in body:
        score += 10
    if len(body) > 500:
        score += 10

    return score

def main():
    best_score = -1
    best_file = None

    for file in QUEUE_DIR.glob("*.json"):
        with open(file) as f:
            data = json.load(f)
        score = score_issue(data)

        with open(SCORED_LOG, "a") as log:
            log.write(f"{file.name}: {score} - {data.get('title')}\n")

        if score > best_score:
            best_score = score
            best_file = file

    if best_file:
        print(f"🎯 Promoting {best_file.name} to active (Score: {best_score})")
        shutil.move(str(best_file), ACTIVE_DIR / best_file.name)
    else:
        print("No valid issues found.")

if __name__ == "__main__":
    main()
