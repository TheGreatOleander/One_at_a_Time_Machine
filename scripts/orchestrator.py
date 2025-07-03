#!/usr/bin/env python3
"""
One-at-a-Time Machine: Swarm Orchestrator
Main coordination engine that brings all components together
"""

import json
import time
import logging
import threading
import subprocess
import os
from pathlib import Path
from datetime import datetime, timezone
from sync_manager import SyncManager
from heartbeat import HeartbeatMonitor
import requests
import re

class SwarmOrchestrator:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.sync_manager = SyncManager(config_path)
        self.heartbeat = HeartbeatMonitor(self.sync_manager)
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = self.sync_manager.config
        
        # State tracking
        self.current_task = None
        self.work_directory = Path(self.config.get("resources", {}).get("work_directory", "work"))
        self.work_directory.mkdir(exist_ok=True)
        
        # GitHub API setup
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_headers = {}
        if self.github_token:
            self.github_headers["Authorization"] = f"token {self.github_token}"
        
        # Rate limiting
        self.last_github_request = 0
        self.github_rate_limit = self.config.get("github_scan", {}).get("rate_limit_delay", 1)
    
    def start(self):
        """Start the orchestrator"""
        self.logger.info("Starting One-at-a-Time Machine Swarm Orchestrator")
        
        # Start heartbeat monitor
        self.heartbeat.start()
        
        # Initial sync
        self.sync_manager.sync_with_network()
        
        # Main coordination loop
        self._coordination_loop()
    
    def stop(self):
        """Stop the orchestrator"""
        self.logger.info("Stopping orchestrator")
        self.heartbeat.stop()
    
    def _coordination_loop(self):
        """Main coordination loop"""
        while True:
            try:
                # Check for new work
                if not self.current_task:
                    self.current_task = self.sync_manager.claim_next_task()
                
                if self.current_task:
                    self.logger.info(f"Working on task: {self.current_task}")
                    success = self._execute_task(self.current_task)
                    
                    if success:
                        self.sync_manager.complete_task(self.current_task)
                        self.logger.info(f"Completed task: {self.current_task}")
                    else:
                        self.logger.error(f"Failed task: {self.current_task}")
                        # TODO: Handle failed tasks (retry, reassign, etc.)
                    
                    self.current_task = None
                
                else:
                    # No tasks available, scan for new ones
                    self.logger.info("No tasks available, scanning for new opportunities")
                    new_tasks = self._scan_for_tasks()
                    
                    if new_tasks:
                        self.sync_manager.add_tasks(new_tasks)
                        self.logger.info(f"Added {len(new_tasks)} new tasks")
                    else:
                        self.logger.info("No new tasks found, waiting...")
                        time.sleep(60)  # Wait 1 minute before scanning again
                
            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal")
                break
            except Exception as e:
                self.logger.error(f"Coordination loop error: {e}")
                time.sleep(30)  # Wait 30 seconds before retrying
        
        self.stop()
    
    def _execute_task(self, task_url: str) -> bool:
        """Execute a single task"""
        try:
            # Parse GitHub issue URL
            issue_info = self._parse_github_url(task_url)
            if not issue_info:
                self.logger.error(f"Invalid GitHub URL: {task_url}")
                return False
            
            owner, repo, issue_number = issue_info
            
            # Fetch issue details
            issue_data = self._fetch_issue_details(owner, repo, issue_number)
            if not issue_data:
                self.logger.error(f"Failed to fetch issue: {task_url}")
                return False
            
            # Create work directory for this task
            task_dir = self.work_directory / f"{owner}_{repo}_{issue_number}"
            task_dir.mkdir(exist_ok=True)
            
            # Clone repository
            if not self._clone_repository(owner, repo, task_dir):
                self.logger.error(f"Failed to clone repository: {owner}/{repo}")
                return False
            
            # Analyze the issue and generate solution
            solution = self._generate_solution(issue_data, task_dir)
            if not solution:
                self.logger.error(f"Failed to generate solution for: {task_url}")
                return False
            
            # Implement the solution
            if not self._implement_solution(solution, task_dir):
                self.logger.error(f"Failed to implement solution for: {task_url}")
                return False
            
            # Create pull request
            if not self._create_pull_request(issue_data, solution, task_dir):
                self.logger.error(f"Failed to create pull request for: {task_url}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Task execution error: {e}")
            return False
    
    def _scan_for_tasks(self) -> list:
        """Scan GitHub for new high-impact issues"""
        try:
            github_config = self.config.get("github_scan", {})
            if not github_config.get("enabled", True):
                return []
            
            # Rate limiting
            now = time.time()
            if now - self.last_github_request < self.github_rate_limit:
                time.sleep(self.github_rate_limit - (now - self.last_github_request))
            
            # Search for issues
            search_queries = self._build_search_queries(github_config)
            all_issues = []
            
            for query in search_queries:
                issues = self._search_github_issues(query)
                all_issues.extend(issues)
            
            # Score and filter issues
            scored_issues = []
            for issue in all_issues:
                score = self._score_issue(issue)
                if score >= github_config.get("min_score", 0.5):
                    scored_issues.append((score, issue["html_url"]))
            
            # Sort by score and return top tasks
            scored_issues.sort(reverse=True)
            max_tasks = github_config.get("max_queue_size", 100)
            
            return [url for score, url in scored_issues[:max_tasks]]
            
        except Exception as e:
            self.logger.error(f"Task scanning error: {e}")
            return []
    
    def _build_search_queries(self, config: dict) -> list:
        """Build GitHub search queries based on configuration"""
        queries = []
        
        languages = config.get("languages", ["python"])
        labels = config.get("labels", ["good first issue", "help wanted"])
        min_stars = config.get("min_stars", 10)
        max_age_days = config.get("max_age_days", 365)
        exclude_orgs = config.get("exclude_orgs", [])
        
        for language in languages:
            for label in labels:
                query_parts = [
                    f"language:{language}",
                    f"label:'{label}'",
                    f"stars:>={min_stars}",
                    f"updated:>{datetime.now().year - 1}-01-01",
                    "state:open",
                    "type:issue"
                ]
                
                # Exclude organizations
                for org in exclude_orgs:
                    query_parts.append(f"-org:{org}")
                
                queries.append(" ".join(query_parts))
        
        return queries
    
    def _search_github_issues(self, query: str) -> list:
        """Search GitHub issues using the API"""
        try:
            self.last_github_request = time.time()
            
            url = "https://api.github.com/search/issues"
            params = {
                "q": query,
                "sort": "updated",
                "order": "desc",
                "per_page": 30
            }
            
            response = requests.get(url, headers=self.github_headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get("items", [])
            
        except requests.RequestException as e:
            self.logger.error(f"GitHub API error: {e}")
            return []
    
    def _score_issue(self, issue: dict) -> float:
        """Score an issue based on potential impact"""
        try:
            weights = self.config.get("scoring", {}).get("weights", {
                "stars": 0.3,
                "activity": 0.2,
                "complexity": 0.2,
                "impact": 0.3
            })
            
            # Extract repository info
            repo_url = issue["repository_url"]
            repo_info = self._fetch_repository_info(repo_url)
            
            if not repo_info:
                return 0.0
            
            # Calculate component scores
            star_score = min(repo_info.get("stargazers_count", 0) / 1000, 1.0)
            activity_score = min(issue.get("comments", 0) / 10, 1.0)
            complexity_score = self._estimate_complexity(issue)
            impact_score = self._estimate_impact(issue, repo_info)
            
            # Weighted total
            total_score = (
                star_score * weights.get("stars", 0.3) +
                activity_score * weights.get("activity", 0.2) +
                complexity_score * weights.get("complexity", 0.2) +
                impact_score * weights.get("impact", 0.3)
            )
            
            return min(total_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Issue scoring error: {e}")
            return 0.0
    
    def _estimate_complexity(self, issue: dict) -> float:
        """Estimate issue complexity (0-1, where 1 is most complex)"""
        title = issue.get("title", "").lower()
        body = issue.get("body", "").lower()
        
        complexity_indicators = {
            "bug": 0.3,
            "fix": 0.3,
            "feature": 0.7,
            "enhancement": 0.6,
            "documentation": 0.2,
            "test": 0.4,
            "refactor": 0.8,
            "performance": 0.9,
            "security": 0.9
        }
        
        max_complexity = 0.0
        for indicator, score in complexity_indicators.items():
            if indicator in title or indicator in body:
                max_complexity = max(max_complexity, score)
        
        return max_complexity if max_complexity > 0 else 0.5
    
    def _estimate_impact(self, issue: dict, repo_info: dict) -> float:
        """Estimate potential impact of fixing this issue"""
        # Factors: repository popularity, issue age, number of thumbs up
        stars = repo_info.get("stargazers_count", 0)
        forks = repo_info.get("forks_count", 0)
        reactions = issue.get("reactions", {}).get("+1", 0)
        
        # Normalize scores
        star_impact = min(stars / 10000, 1.0)
        fork_impact = min(forks / 1000, 1.0)
        reaction_impact = min(reactions / 20, 1.0)
        
        return (star_impact * 0.5 + fork_impact * 0.3 + reaction_impact * 0.2)
    
    def _parse_github_url(self, url: str) -> tuple:
        """Parse GitHub issue URL into owner, repo, issue_number"""
        pattern = r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)"
        match = re.match(pattern, url)
        
        if match:
            return match.group(1), match.group(2), int(match.group(3))
        
        return None
    
    def _fetch_issue_details(self, owner: str, repo: str, issue_number: int) -> dict:
        """Fetch detailed issue information"""
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
            response = requests.get(url, headers=self.github_headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch issue details: {e}")
            return None
    
    def _fetch_repository_info(self, repo_url: str) -> dict:
        """Fetch repository information"""
        try:
            response = requests.get(repo_url, headers=self.github_headers)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch repository info: {e}")
            return None
    
    def _clone_repository(self, owner: str, repo: str, task_dir: Path) -> bool:
        """Clone repository to working directory"""
        try:
            repo_dir = task_dir / "repo"
            if repo_dir.exists():
                # Repository already cloned
                return True
            
            clone_url = f"https://github.com/{owner}/{repo}.git"
            subprocess.run(["git", "clone", clone_url, str(repo_dir)], 
                         check=True, capture_output=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to clone repository: {e}")
            return False
    
    def _generate_solution(self, issue_data: dict, task_dir: Path) -> dict:
        """Generate solution for the issue using AI"""
        # This is a placeholder - in a real implementation, this would:
        # 1. Analyze the issue description and repository code
        # 2. Generate a solution specification
        # 3. Create implementation plan
        # 4. Return structured solution data
        
        solution = {
            "issue_title": issue_data.get("title"),
            "issue_body": issue_data.get("body"),
            "solution_type": "feature",  # bug, feature, documentation, etc.
            "files_to_modify": [],
            "implementation_plan": [],
            "test_plan": []
        }
        
        # Save solution to task directory
        solution_file = task_dir / "solution.json"
        with open(solution_file, 'w') as f:
            json.dump(solution, f, indent=2)
        
        return solution
    
    def _implement_solution(self, solution: dict, task_dir: Path) -> bool:
        """Implement the generated solution"""
        # This is a placeholder - in a real implementation, this would:
        # 1. Execute the implementation plan
        # 2. Modify the necessary files
        # 3. Run tests
        # 4. Verify the solution works
        
        self.logger.info("Implementing solution (placeholder)")
        return True
    
    def _create_pull_request(self, issue_data: dict, solution: dict, task_dir: Path) -> bool:
        """Create pull request for the solution"""
        # This is a placeholder - in a real implementation, this would:
        # 1. Create a new branch
        # 2. Commit the changes
        # 3. Push the branch
        # 4. Create pull request via GitHub API
        
        self.logger.info("Creating pull request (placeholder)")
        return True

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="One-at-a-Time Machine Swarm Orchestrator")
    parser.add_argument("--config", default="config.json", help="Configuration file path")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start orchestrator
    orchestrator = SwarmOrchestrator(args.config)
    
    try:
        orchestrator.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
        orchestrator.stop()

if __name__ == "__main__":
    main()
