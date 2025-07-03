#!/usr/bin/env python3
"""
GitHub Issue Scanner - One-at-a-Time Machine
Discovers and evaluates high-impact GitHub issues for the queue
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os

class GitHubScanner:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.base_url = "https://api.github.com"
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'One-at-a-Time-Machine/1.0'
        }
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'
        
        self.rate_limit_remaining = 60  # GitHub's unauthenticated limit
        self.rate_limit_reset = time.time() + 3600

    def check_rate_limit(self):
        """Check and respect GitHub API rate limits"""
        if self.rate_limit_remaining <= 5:
            sleep_time = max(0, self.rate_limit_reset - time.time())
            if sleep_time > 0:
                print(f"Rate limit low. Sleeping {sleep_time:.0f} seconds...")
                time.sleep(sleep_time)

    def make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated GitHub API request with rate limiting"""
        self.check_rate_limit()
        
        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        
        # Update rate limit info
        self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', time.time() + 3600))
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error {response.status_code}: {response.text}")
            return {}

    def get_trending_repos(self, language: str = None, min_stars: int = 100) -> List[Dict]:
        """Find trending repositories with active issues"""
        params = {
            'q': f'stars:>{min_stars} pushed:>2024-01-01',
            'sort': 'stars',
            'order': 'desc',
            'per_page': 50
        }
        
        if language:
            params['q'] += f' language:{language}'
        
        data = self.make_request('search/repositories', params)
        return data.get('items', [])

    def get_repo_issues(self, repo_full_name: str, limit: int = 30) -> List[Dict]:
        """Get open issues from a specific repository"""
        params = {
            'state': 'open',
            'sort': 'created',
            'direction': 'desc',
            'per_page': limit
        }
        
        endpoint = f'repos/{repo_full_name}/issues'
        issues = self.make_request(endpoint, params)
        
        # Filter out pull requests (they appear as issues in the API)
        return [issue for issue in issues if 'pull_request' not in issue]

    def calculate_impact_score(self, issue: Dict, repo: Dict) -> float:
        """Calculate impact score for an issue"""
        score = 0.0
        
        # Repository popularity (0-40 points)
        stars = repo.get('stargazers_count', 0)
        forks = repo.get('forks_count', 0)
        score += min(40, (stars / 100) + (forks / 20))
        
        # Issue engagement (0-30 points)
        comments = issue.get('comments', 0)
        reactions = issue.get('reactions', {}).get('total_count', 0)
        score += min(30, (comments * 2) + (reactions * 3))
        
        # Issue age and activity (0-20 points)
        created = datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00'))
        age_days = (datetime.now().astimezone() - created).days
        if age_days < 30:
            score += 20  # Recent issues get full points
        elif age_days < 90:
            score += 15  # Moderately old issues
        elif age_days < 365:
            score += 10  # Older issues
        else:
            score += 5   # Very old issues
        
        # Labels indicating importance (0-10 points)
        labels = [label['name'].lower() for label in issue.get('labels', [])]
        important_labels = ['bug', 'enhancement', 'feature', 'security', 'performance']
        score += min(10, len([l for l in labels if any(imp in l for imp in important_labels)]) * 3)
        
        return round(score, 2)

    def scan_for_issues(self, languages: List[str] = None, max_repos: int = 20) -> List[Dict]:
        """Main scanning function to find high-impact issues"""
        if not languages:
            languages = ['python', 'javascript', 'java', 'go', 'rust']
        
        all_issues = []
        
        for language in languages:
            print(f"Scanning {language} repositories...")
            repos = self.get_trending_repos(language)
            
            for repo in repos[:max_repos]:
                repo_name = repo['full_name']
                print(f"  Checking issues in {repo_name}...")
                
                issues = self.get_repo_issues(repo_name)
                
                for issue in issues:
                    impact_score = self.calculate_impact_score(issue, repo)
                    
                    # Only queue issues with decent impact scores
                    if impact_score >= 25:
                        enriched_issue = {
                            'id': issue['id'],
                            'title': issue['title'],
                            'url': issue['html_url'],
                            'api_url': issue['url'],
                            'body': issue['body'][:1000] if issue['body'] else '',
                            'repo': repo_name,
                            'repo_stars': repo['stargazers_count'],
                            'repo_forks': repo['forks_count'],
                            'labels': [l['name'] for l in issue.get('labels', [])],
                            'comments_count': issue.get('comments', 0),
                            'created_at': issue['created_at'],
                            'impact_score': impact_score,
                            'discovered_at': datetime.now().isoformat()
                        }
                        all_issues.append(enriched_issue)
                
                # Small delay to be respectful
                time.sleep(0.5)
        
        # Sort by impact score
        all_issues.sort(key=lambda x: x['impact_score'], reverse=True)
        return all_issues

    def save_queue(self, issues: List[Dict], filename: str = 'queue.json'):
        """Save discovered issues to queue file"""
        with open(filename, 'w') as f:
            json.dump({
                'updated_at': datetime.now().isoformat(),
                'total_issues': len(issues),
                'issues': issues
            }, f, indent=2)
        print(f"Saved {len(issues)} issues to {filename}")

def main():
    """Main execution function"""
    scanner = GitHubScanner()
    
    print("🔍 One-at-a-Time Machine - GitHub Issue Scanner")
    print("=" * 50)
    
    # Scan for high-impact issues
    issues = scanner.scan_for_issues()
    
    if issues:
        print(f"\n✅ Found {len(issues)} high-impact issues")
        print("\nTop 5 Issues:")
        for i, issue in enumerate(issues[:5], 1):
            print(f"{i}. [{issue['impact_score']:.1f}] {issue['title']}")
            print(f"   {issue['repo']} - {issue['url']}")
        
        # Save to queue
        scanner.save_queue(issues)
        
        # Update status
        status = f"""# One-at-a-Time Machine Status

## Current Phase: Issue Discovery Complete
- **Last Scan**: {datetime.now().isoformat()}
- **Issues Found**: {len(issues)}
- **Top Issue**: {issues[0]['title']} (Score: {issues[0]['impact_score']})

## Next Step: Generate Specification
The system should now generate a detailed specification for the top-priority issue:
- **Issue**: {issues[0]['title']}
- **Repository**: {issues[0]['repo']}
- **URL**: {issues[0]['url']}
- **Impact Score**: {issues[0]['impact_score']}

## Queue Status
{len(issues)} issues ready for processing in `queue.json`
"""
        
        with open('status.md', 'w') as f:
            f.write(status)
        
        print(f"\n📋 Status updated. Next: Generate spec for top issue")
    else:
        print("❌ No high-impact issues found")

if __name__ == "__main__":
    main()
