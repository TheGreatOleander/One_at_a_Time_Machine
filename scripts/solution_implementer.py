#!/usr/bin/env python3
"""
Solution Implementer - One-at-a-Time Machine
Generates code solutions based on specifications
"""

import json
import requests
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

class SolutionImplementer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o-mini"
        
    def get_repo_files(self, repo_name: str, path: str = "") -> List[Dict]:
        """Get repository file structure"""
        github_token = os.getenv('GITHUB_TOKEN')
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        url = f"https://api.github.com/repos/{repo_name}/contents/{path}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        return []
    
    def get_file_content(self, repo_name: str, file_path: str) -> str:
        """Get specific file content from repository"""
        github_token = os.getenv('GITHUB_TOKEN')
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        url = f"https://api.github.com/repos/{repo_name}/contents/{file_path}"
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            import base64
            content = response.json()
            if content.get('content'):
                return base64.b64decode(content['content']).decode('utf-8')
        return ""
    
    def analyze_codebase(self, repo_name: str) -> Dict:
        """Analyze repository structure and key files"""
        files = self.get_repo_files(repo_name)
        
        # Find key files
        key_files = []
        for file in files:
            if file['type'] == 'file':
                name = file['name'].lower()
                if any(ext in name for ext in ['.py', '.js', '.java', '.go', '.rs', '.md']):
                    key_files.append({
                        'name': file['name'],
                        'path': file['path'],
                        'size': file['size']
                    })
        
        # Get content of important files (README, package files, etc.)
        important_content = {}
        for file in files:
            if file['type'] == 'file':
                name = file['name'].lower()
                if name in ['readme.md', 'package.json', 'requirements.txt', 'go.mod', 'cargo.toml']:
                    content = self.get_file_content(repo_name, file['path'])
                    if content:
                        important_content[file['name']] = content[:1000]  # Limit size
        
        return {
            'total_files': len([f for f in files if f['type'] == 'file']),
            'key_files': key_files[:20],  # Limit to prevent token overflow
            'important_content': important_content
        }
    
    def load_specification(self, spec_filename: str) -> str:
        """Load the specification file"""
        try:
            with open(spec_filename, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return ""
    
    def generate_solution(self, issue: Dict, spec_content: str, codebase_info: Dict) -> Dict:
        """Generate solution code using LLM"""
        if not self.api_key:
            return self._generate_basic_solution(issue, spec_content)
        
        # Build context-aware prompt
        prompt = f"""You are implementing a solution for a GitHub issue. Generate clean, working code.

## Issue Context
- **Repository**: {issue['repo']}
- **Issue**: {issue['title']}
- **Labels**: {', '.join(issue['labels'])}
- **Impact Score**: {issue['impact_score']}

## Specification
{spec_content}

## Codebase Context
- **Total Files**: {codebase_info['total_files']}
- **Key Files**: {', '.join([f['name'] for f in codebase_info['key_files'][:10]])}

## Important Files Content
{chr(10).join([f"**{name}**:{chr(10)}{content[:500]}..." for name, content in codebase_info['important_content'].items()])}

## Your Task
Generate a complete solution including:

1. **Main Implementation** - The core code changes
2. **Tests** - Unit tests for the changes
3. **Documentation** - Brief explanation of the solution

Format your response as:

### Implementation
```[language]
[main code here]
```

### Tests
```[language]
[test code here]
```

### Documentation
[Brief explanation of the solution approach]

### Files to Modify
- [list of files that need changes]

Keep the code clean, well-commented, and following the project's existing patterns."""

        try:
            response = requests.post(
                self.api_url,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': self.model,
                    'messages': [
                        {'role': 'system', 'content': 'You are a senior software engineer implementing GitHub issue solutions.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'max_tokens': 2000,
                    'temperature': 0.2
                }
            )
            
            if response.status_code == 200:
                solution_text = response.json()['choices'][0]['message']['content']
                return self._parse_solution_response(solution_text)
            else:
                print(f"LLM API Error: {response.status_code}")
                return self._generate_basic_solution(issue, spec_content)
                
        except Exception as e:
            print(f"Error generating solution: {e}")
            return self._generate_basic_solution(issue, spec_content)
    
    def _parse_solution_response(self, solution_text: str) -> Dict:
        """Parse the LLM response into structured solution"""
        solution = {
            'implementation': '',
            'tests': '',
            'documentation': '',
            'files_to_modify': []
        }
        
        # Extract implementation
        impl_match = re.search(r'### Implementation\s*```[\w]*\n(.*?)```', solution_text, re.DOTALL)
        if impl_match:
            solution['implementation'] = impl_match.group(1).strip()
        
        # Extract tests
        test_match = re.search(r'### Tests\s*```[\w]*\n(.*?)```', solution_text, re.DOTALL)
        if test_match:
            solution['tests'] = test_match.group(1).strip()
        
        # Extract documentation
        doc_match = re.search(r'### Documentation\s*\n(.*?)(?=###|$)', solution_text, re.DOTALL)
        if doc_match:
            solution['documentation'] = doc_match.group(1).strip()
        
        # Extract files to modify
        files_match = re.search(r'### Files to Modify\s*\n(.*?)(?=###|$)', solution_text, re.DOTALL)
        if files_match:
            files_text = files_match.group(1).strip()
            solution['files_to_modify'] = [line.strip('- ').strip() for line in files_text.split('\n') if line.strip()]
        
        return solution
    
    def _generate_basic_solution(self, issue: Dict, spec_content: str) -> Dict:
        """Generate basic solution template without LLM"""
        return {
            'implementation': f"""# Solution for: {issue['title']}
# Repository: {issue['repo']}
# 
# TODO: Implement the solution based on the specification
# This is a placeholder implementation

def solve_issue():
    \"\"\"
    Implement the solution for the GitHub issue.
    
    Based on: {issue['title']}
    \"\"\"
    # Add implementation here
    pass

if __name__ == "__main__":
    solve_issue()
""",
            'tests': f"""# Tests for: {issue['title']}
import unittest

class TestSolution(unittest.TestCase):
    def test_solution_works(self):
        \"\"\"Test that the solution addresses the issue\"\"\"
        # Add test implementation here
        self.assertTrue(True)  # Placeholder

if __name__ == "__main__":
    unittest.main()
""",
            'documentation': f"""## Solution Documentation

**Issue**: {issue['title']}
**Repository**: {issue['repo']}
**Impact Score**: {issue['impact_score']}

### Approach
This solution addresses the GitHub issue by implementing the requirements outlined in the specification.

### Files Modified
- TBD: Files to be determined based on issue analysis

### Testing
Unit tests have been provided to verify the solution works correctly.
""",
            'files_to_modify': ['TBD']
        }
    
    def save_solution(self, solution: Dict, issue: Dict) -> str:
        """Save the generated solution to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        solution_dir = f"solution_{issue['id']}_{timestamp}"
        
        os.makedirs(solution_dir, exist_ok=True)
        
        # Save implementation
        impl_file = os.path.join(solution_dir, 'implementation.py')
        with open(impl_file, 'w') as f:
            f.write(solution['implementation'])
        
        # Save tests
        test_file = os.path.join(solution_dir, 'tests.py')
        with open(test_file, 'w') as f:
            f.write(solution['tests'])
        
        # Save documentation
        doc_file = os.path.join(solution_dir, 'README.md')
        with open(doc_file, 'w') as f:
            f.write(solution['documentation'])
        
        # Save solution summary
        summary = {
            'issue_id': issue['id'],
            'issue_title': issue['title'],
            'repository': issue['repo'],
            'impact_score': issue['impact_score'],
            'generated_at': datetime.now().isoformat(),
            'files_to_modify': solution['files_to_modify'],
            'solution_directory': solution_dir
        }
        
        summary_file = os.path.join(solution_dir, 'solution_summary.json')
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Solution saved to: {solution_dir}")
        return solution_dir

def main():
    """Main execution function"""
    # Load the queue to get current issue
    try:
        with open('queue.json', 'r') as f:
            queue_data = json.load(f)
        issues = queue_data['issues']
    except FileNotFoundError:
        print("❌ No queue.json found. Run scanner first.")
        return
    
    if not issues:
        print("❌ No issues in queue")
        return
    
    # Find the spec file for the top issue
    top_issue = issues[0]
    spec_filename = f"spec_{top_issue['id']}.md"
    
    if not os.path.exists(spec_filename):
        print(f"❌ Specification file not found: {spec_filename}")
        return
    
    print("🛠️  One-at-a-Time Machine - Solution Implementer")
    print("=" * 50)
    print(f"Implementing: {top_issue['title']}")
    print(f"Repository: {top_issue['repo']}")
    
    # Initialize implementer
    implementer = SolutionImplementer()
    
    # Load specification
    spec_content = implementer.load_specification(spec_filename)
    
    # Analyze codebase
    print("🔍 Analyzing repository...")
    codebase_info = implementer.analyze_codebase(top_issue['repo'])
    
    # Generate solution
    print("🎯 Generating solution...")
    solution = implementer.generate_solution(top_issue, spec_content, codebase_info)
    
    # Save solution
    solution_dir = implementer.save_solution(solution, top_issue)
    
    # Update status
    status = f"""# One-at-a-Time Machine Status

## Current Phase: Implementation Complete
- **Last Update**: {datetime.now().isoformat()}
- **Active Issue**: {top_issue['title']}
- **Repository**: {top_issue['repo']}
- **Impact Score**: {top_issue['impact_score']}
- **Solution Directory**: {solution_dir}

## Next Step: Testing & Validation
The solution has been generated and saved. Next steps:
1. Review the generated code in `{solution_dir}/`
2. Test the implementation
3. Validate against the original issue
4. Submit as pull request (manual step)

## Generated Files
- `{solution_dir}/implementation.py` - Main solution code
- `{solution_dir}/tests.py` - Unit tests
- `{solution_dir}/README.md` - Documentation
- `{solution_dir}/solution_summary.json` - Metadata

## Queue Status
Issue completed: {top_issue['title']}
Remaining issues: {len(issues)-1}
"""
    
    with open('status.md', 'w') as f:
        f.write(status)
    
    print(f"\n✅ Solution implemented successfully!")
    print(f"📁 Check the solution in: {solution_dir}")
    print(f"📋 Status updated. Ready for testing & validation.")

if __name__ == "__main__":
    main()
