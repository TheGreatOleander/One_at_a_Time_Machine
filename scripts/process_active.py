import os
import json
from pathlib import Path

ACTIVE_DIR = Path("ideas/active")
TEMPLATE_PATH = Path("prompts/01_spec_prompt.md")
OUTPUT_PROMPT_PATH = ACTIVE_DIR / "spec_prompt.md"

def find_active_issue():
    files = list(ACTIVE_DIR.glob("*.json"))
    if not files:
        print("❌ No active issues found.")
        return None
    return files[0]

def load_template():
    if not TEMPLATE_PATH.exists():
        print("❌ Prompt template not found.")
        return None
    return TEMPLATE_PATH.read_text()

def build_prompt(template, issue_data):
    return template.format(
        title=issue_data.get("title", "No title"),
        body=issue_data.get("body", "No body text"),
        url=issue_data.get("html_url", "No URL"),
        comments=issue_data.get("comments", 0)
    )

def main():
    active_issue_path = find_active_issue()
    if not active_issue_path:
        return

    with open(active_issue_path) as f:
        issue_data = json.load(f)

    template = load_template()
    if not template:
        return

    prompt = build_prompt(template, issue_data)
    OUTPUT_PROMPT_PATH.write_text(prompt)

    print("✅ Prompt generated at:")
    print(f"   {OUTPUT_PROMPT_PATH.resolve()}")
    print("\n🔽 Prompt Preview:\n" + "-" * 40)
    print(prompt[:1500])  # Prevents overflow
    print("-" * 40)
    print("📋 Copy this into ChatGPT, then save response as `spec.md`.")

if __name__ == "__main__":
    main()
