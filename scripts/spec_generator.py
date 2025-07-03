#!/usr/bin/env python3
"""
Specification Generator - One-at-a-Time Machine
Converts GitHub issues into structured specifications using LLM
"""

import json
import requests
import os
from datetime import datetime
from typing import Dict, Optional

class SpecGenerator:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.model = "gpt-4o-mini"  # Cost-effective option
        
    def get_repo_context(self, repo_name: str) -> Dict:
        """Fetch repository context for better specification"""
        github_token = os.getenv('GITHUB_TOKEN')
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        
        # Get repository info
        repo_url = f"https://api.github.com/repos/{repo_name}"
        repo_response = requests.get(repo_url, headers=headers)
        repo_data = repo_response.json() if repo_response.status_code == 200 else {}
        
        # Get recent commits for tech stack hints
        commits_url = f"https://api.github.com/repos/{repo_name}/commits?per_page=5"
        commits_response = requests.get(commits_url, headers=headers)
        commits_data = commits_response.json() if commits_response.status_code == 200 else []
        
        # Get repository structure
        contents_url = f"https://api.github.com/repos/{repo_name}/contents"
        contents_response = requests.get(contents_url, headers=headers)
        contents_data = contents_response.json() if contents_response.status_code == 200 else []
        
        return {
            'description': repo_data.get('description', ''),
            'language': repo_data.get('language', ''),
            'topics': repo_data.get('topics', []),
            'recent_commits': [c.get('commit', {}).get('message', '') for c in commits_data[:3]],
            'root_files': [f['name'] for f in contents_data if f['type'] == 'file']
        }

    def generate_specification(self, issue: Dict) -> str:
        """Generate detailed specification using LLM"""
        if not self.api_key:
            return self._generate_basic_spec(issue)
        
        # Get repository context
        repo_context = self.get_repo_context(issue['repo'])
        
        # Build the prompt
        prompt = f"""You are part of a decentralized AI-human system designed to solve high-impact GitHub issues one at a time.

Generate a clear, structured software specification for this GitHub issue:

## Issue Details
- **Title**: {issue['title']}
- **Repository**: {issue['repo']}
- **URL**: {issue['url']}
- **Impact Score**: {issue['impact_score']}
- **Labels**: {', '.join(issue['labels'])}
- **Description**: {issue['body']}

## Repository Context
- **Language**: {repo_context['language']}
- **Description**: {repo_context['description']}
- **Topics**: {', '.join(repo_context['topics'])}
- **Recent Activity**: {'; '.join(repo_context['recent_commits'])}
- **Root Files**: {', '.join(repo_context['root_files'][:10])}

## Your Task
Generate a specification in this exact format:

# Specification: [Issue Title]

## Overview
[Brief description of what needs to be solved]

## Goals
[Specific, measurable objectives]

## User Impact
[How this solution helps users]

## System Components
[What parts of the system are involved]

## Implementation Sketch
[High-level approach with key steps]

## Technical Requirements
[Specific technical constraints and requirements]

## Testing Strategy
[How to verify the solution works]

## Definition of Done
[Clear criteria for completion]

Keep it concise but complete. Focus on actionable technical details."""

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
                        {'role': 'system', 'content': 'You are a technical specification generator for software issues.'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'max_tokens': 1500,
                    'temperature': 0.3
                }
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                print(f"LLM API Error: {response.status_code}")
                return self._generate_basic_spec(issue)
                
        except Exception as e:
            print(f"Error generating spec: {e}")
            return self._generate_basic_spec(issue)

    def _generate_basic_spec(self, issue: Dict) -> str:
        """Generate basic specification without LLM"""
        return f"""# Specification: {issue['title']}

## Overview
Address the GitHub issue: {issue['title']} in repository {issue['repo']}.

## Goals
- Resolve the reported issue
- Maintain code quality and consistency
- Ensure solution is well-tested

## User Impact
- **Repository**: {issue['repo']} ({issue['repo_stars']} stars, {issue['repo_forks']} forks)
- **Impact Score**: {issue['impact_score']}
- **Labels**: {', '.join(issue['labels'])}

## System Components
Based on repository: {issue['repo']}
- Primary language: To be determined from codebase analysis
- Files affected: To be identified during implementation

## Implementation Sketch
1. Analyze the issue requirements
2. Identify affected code sections
3. Implement solution following project conventions
4. Add appropriate tests
5. Update documentation if needed

## Technical Requirements
- Follow existing code style and patterns
- Maintain backward compatibility
- Add unit tests for new functionality
- Update relevant documentation

## Testing Strategy
- Unit tests for new/modified functions
- Integration tests if applicable
- Manual testing of the reported scenario
- Regression testing of related functionality

## Definition of Done
- Issue requirements fully addressed
- All tests pass
- Code review standards met
- Documentation updated
- Solution validated against original issue

## Issue Details
- **URL**: {issue['url']}
- **Created**: {issue['created_at']}
- **Comments**: {issue['comments_count']}
- **Description**: {issue['body'][:500]}{'...' if len(issue['body']) > 500 else ''}
"""

    def save_specification(self, spec: str, issue: Dict):
        """Save specification to file"""
        filename = f"spec_{issue['id']}.md"
        with open(filename, 'w') as f:
            f.write(spec)
        print(f"Specification saved to {filename}")
        return filename

def main():
    """Main execution function"""
    # Load the queue
    try:
        with open('queue.json', 'r') as f:
            queue_data = json.load(f)
        issues = queue_data['issues']
    except FileNotFoundError:
        print("❌ No queue.json found. Run scanner first.")
        return
    except Exception as e:
        print(f"❌ Error loading queue: {e}")
        return
    
    if not issues:
        print("❌ No issues in queue")
        return
    
    print("🔮 One-at-a-Time Machine - Specification Generator")
    print("=" * 50)
    
    # Get the top issue
    top_issue = issues[0]
    print(f"Generating spec for: {top_issue['title']}")
    print(f"Repository: {top_issue['repo']}")
    print(f"Impact Score: {top_issue['impact_score']}")
    
    # Generate specification
    generator = SpecGenerator()
    spec = generator.generate_specification(top_issue)
    
    # Save specification
    spec_filename = generator.save_specification(spec, top_issue)
    
    # Update status
    status = f"""# One-at-a-Time Machine Status

## Current Phase: Specification Complete
- **Last Update**: {datetime.now().isoformat()}
- **Active Issue**: {top_issue['title']}
- **Repository**: {top_issue['repo']}
- **Impact Score**: {top_issue['impact_score']}
- **Specification**: {spec_filename}

## Next Step: Implementation
The system should now implement the solution based on the specification:
- Review the specification in `{spec_filename}`
- Analyze the repository structure
- Implement the solution following the spec
- Create tests and documentation

## Current Task Details
- **Issue URL**: {top_issue['url']}
- **Labels**: {', '.join(top_issue['labels'])}
- **Comments**: {top_issue['comments_count']}
- **Discovered**: {top_issue['discovered_at']}

## Queue Status
{len(issues)} total issues, 1 active, {len(issues)-1} pending
"""
    
    with open('status.md', 'w') as f:
        f.write(status)
    
    print(f"\n✅ Specification generated successfully")
    print(f"📋 Status updated. Next: Implement solution")
    print(f"📝 Spec saved as: {spec_filename}")

if __name__ == "__main__":
    main()
