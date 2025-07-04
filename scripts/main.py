#!/usr/bin/env python3
"""
One-at-a-Time Machine: Main Node Controller
Integrates sync management and heartbeat for coordinated swarm operation
"""

import time
import json
import sys
import requests
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from sync_manager import SyncManager
from heartbeat import HeartbeatManager

class OTATMNode:
    def __init__(self, config_path="config.json"):
        self.config = self._load_config(config_path)
        self.sync_manager = SyncManager(
            sync_method=self.config.get("sync_method", "git"),
            sync_config=self.config.get("sync_config", {})
        )
        self.heartbeat = HeartbeatManager(self.sync_manager)
        
        # Runtime state
        self.current_task = None
        self.work_dir = Path("work")
        self.work_dir.mkdir(exist_ok=True)
        
        print(f"[OTATM] Node initialized: {self.sync_manager.device_id}")
    
    def _load_config(self, config_path):
        """Load configuration file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Create default config
            default_config = {
                "sync_method": "git",
                "sync_config": {},
                "github_token": None,
                "scan_interval": 3600,
                "max_concurrent_tasks": 1,
                "task_timeout": 7200,
                "priority_keywords": ["bug", "enhancement", "help-wanted"],
                "exclude_keywords": ["wontfix", "duplicate", "invalid"]
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def start(self):
        """Start the node"""
        print(f"[OTATM] Starting One-at-a-Time Machine node...")
        
        # Start heartbeat system
        self.heartbeat.start()
        
        # Initial sync
        print("[OTATM] Performing initial sync...")
        self.sync_manager.sync_with_network()
        
        # Main work loop
        try:
            self._main_loop()
        finally:
            self.heartbeat.stop()
    
    def _main_loop(self):
        """Main node operation loop"""
        while True:
            try:
                # Check for available tasks
                task_url = self.sync_manager.claim_next_task()
                
                if task_url:
                    self._work_on_task(task_url)
                else:
                    # No tasks available, discover new ones
                    self._discover_tasks()
                    
                    # Brief idle period
                    self.heartbeat.update_status("idle")
                    time.sleep(60)
                
            except KeyboardInterrupt:
                print("\n[OTATM] Shutdown requested...")
                break
            except Exception as e:
                print(f"[OTATM] Error in main loop: {e}")
                time.sleep(30)
    
    def _work_on_task(self, task_url):
        """Work on a specific task"""
        self.current_task = task_url
        self.heartbeat.update_status("working", task_url)
        
        print(f"[OTATM] Working on task: {task_url}")
        
        try:
            # Fetch task details
            task_data = self._fetch_task_details(task_url)
            if not task_data:
                print(f"[OTATM] Failed to fetch task details: {task_url}")
                self.sync_manager.complete_task(task_url)
                return
            
            # Create work directory for this task
            task_id = task_url.split('/')[-1]
            task_dir = self.work_dir / f"task_{task_id}"
            task_dir.mkdir(exist_ok=True)
            
            # Generate specification
            spec_path = task_dir / "spec.md"
            if not spec_path.exists():
                print(f"[OTATM] Generating specification...")
                spec_content = self._generate_specification(task_data)
                spec_path.write_text(spec_content)
            
            # Work on the task
            success = self._execute_task(task_dir, task_data)
            
            if success:
                print(f"[OTATM] Task completed successfully: {task_url}")
                self.sync_manager.complete_task(task_url)
            else:
                print(f"[OTATM] Task failed: {task_url}")
                # For now, still mark as complete to avoid infinite retries
                self.sync_manager.complete_task(task_url)
                
        except Exception as e:
            print(f"[OTATM] Error working on task {task_url}: {e}")
            self.sync_manager.complete_task(task_url)
        
        finally:
            self.current_task = None
    
    def _fetch_task_details(self, task_url):
        """Fetch GitHub issue details"""
        try:
            # Extract repo and issue number from URL
            # Example: https://github.com/owner/repo/issues/123
            parts = task_url.split('/')
            if len(parts) < 7:
                return None
            
            owner = parts[3]
            repo = parts[4]
            issue_num = parts[6]
            
            # GitHub API request
            api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}"
            headers = {}
            
            if self.config.get("github_token"):
                headers["Authorization"] = f"token {self.config['github_token']}"
            
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            print(f"[OTATM] Failed to fetch task details: {e}")
            return None
    
    def _generate_specification(self, task_data):
        """Generate task specification"""
        title = task_data.get("title", "Unknown Task")
        body = task_data.get("body", "No description provided")
        labels = [label["name"] for label in task_data.get("labels", [])]
        
        spec = f"""# Task Specification: {title}

## Overview
{body}

## Labels
{', '.join(labels) if labels else 'None'}

## Goals
- Analyze the issue requirements
- Implement a solution
- Test the implementation
- Document the changes

## Implementation Notes
- Repository: {task_data.get("repository_url", "Unknown")}
- Issue URL: {task_data.get("html_url", "Unknown")}
- Created: {task_data.get("created_at", "Unknown")}
- Updated: {task_data.get("updated_at", "Unknown")}

## Status
- [ ] Analysis complete
- [ ] Implementation complete
- [ ] Testing complete
- [ ] Documentation complete
"""
        
        return spec
    
    def _execute_task(self, task_dir, task_data):
        """Execute the task implementation"""
        # This is a placeholder for the actual task execution
        # In a real implementation, this would:
        # 1. Clone the repository
        # 2. Analyze the codebase
        # 3. Implement the solution
        # 4. Run tests
        # 5. Create pull request
        
        print(f"[OTATM] Executing task in {task_dir}")
        
        # For now, just simulate work
        for i in range(5):
            print(f"[OTATM] Working... {i+1}/5")
            time.sleep(10)  # Simulate work
        
        # Create a simple result file
        result_file = task_dir / "result.txt"
        result_file.write_text(f"Task completed at {datetime.now()}\n")
        
        return True
    
    def _discover_tasks(self):
        """Discover new tasks from GitHub"""
        print("[OTATM] Discovering new tasks...")
        
        try:
            # Search for issues across popular repositories
            search_queries = [
                "is:issue is:open label:bug",
                "is:issue is:open label:enhancement", 
                "is:issue is:open label:help-wanted"
            ]
            
            new_tasks = []
            
            for query in search_queries:
                tasks = self._search_github_issues(query)
                new_tasks.extend(tasks)
                
                # Rate limiting
                time.sleep(1)
            
            # Remove duplicates and score tasks
            unique_tasks = list(set(new_tasks))
            scored_tasks = self._score_tasks(unique_tasks)
            
            # Add high-scoring tasks to queue
            high_priority = [task for task, score in scored_tasks if score > 0.5]
            
            if high_priority:
                self.sync_manager.add_tasks_to_queue(high_priority)
                print(f"[OTATM] Added {len(high_priority)} new tasks to queue")
            
        except Exception as e:
            print(f"[OTATM] Error discovering tasks: {e}")
    
    def _search_github_issues(self, query, max_results=20):
        """Search GitHub for issues"""
        try:
            api_url = "https://api.github.com/search/issues"
            params = {
                "q": query,
                "sort": "updated",
                "per_page": max_results
            }
            
            headers = {}
            if self.config.get("github_token"):
                headers["Authorization"] = f"token {self.config['github_token']}"
            
            response = requests.get(api_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return [item["html_url"] for item in data.get("items", [])]
            
        except Exception as e:
            print(f"[OTATM] Error searching GitHub: {e}")
            return []
    
    def _score_tasks(self, task_urls):
        """Score tasks by potential impact"""
        scored_tasks = []
        
        for task_url in task_urls:
            try:
                task_data = self._fetch_task_details(task_url)
                if not task_data:
                    continue
                
                score = self._calculate_task_score(task_data)
                scored_tasks.append((task_url, score))
                
            except Exception as e:
                print(f"[OTATM] Error scoring task {task_url}: {e}")
                continue
        
        # Sort by score (highest first)
        scored_tasks.sort(key=lambda x: x[1], reverse=True)
        return scored_tasks
    
    def _calculate_task_score(self, task_data):
        """Calculate task priority score"""
        score = 0.0
        
        # Base score
        score += 0.1
        
        # Label scoring
        labels = [label["name"].lower() for label in task_data.get("labels", [])]
        
        for keyword in self.config.get("priority_keywords", []):
            if keyword.lower() in labels:
                score += 0.2
        
        for keyword in self.config.get("exclude_keywords", []):
            if keyword.lower() in labels:
                score -= 0.5
        
        # Engagement scoring
        comments = task_data.get("comments", 0)
        if comments > 0:
            score += min(comments * 0.05, 0.3)
        
        # Repository popularity (if available)
        # This would require additional API calls
        
        # Age scoring (newer issues get slight boost)
        try:
            created_at = datetime.fromisoformat(task_data["created_at"].replace('Z', '+00:00'))
            age_days = (datetime.now(timezone.utc) - created_at).days
            
            if age_days < 7:
                score += 0.1
            elif age_days > 365:
                score -= 0.1
        except:
            pass
        
        return max(0.0, min(1.0, score))
    
    def get_status(self):
        """Get current node status"""
        swarm_status = self.sync_manager.get_swarm_status()
        network_health = self.heartbeat.get_network_health()
        
        return {
            "device_id": self.sync_manager.device_id,
            "current_task": self.current_task,
            "swarm_status": swarm_status,
            "network_health": network_health,
            "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0
        }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="One-at-a-Time Machine Node")
    parser.add_argument("--config", default="config.json", help="Configuration file")
    parser.add_argument("--status", action="store_true", help="Show status and exit")
    parser.add_argument("--sync", action="store_true", help="Sync with network and exit")
    parser.add_argument("--discover", action="store_true", help="Discover tasks and exit")
    
    args = parser.parse_args()
    
    # Initialize node
    node = OTATMNode(args.config)
    
    if args.status:
        status = node.get_status()
        print(json.dumps(status, indent=2))
        return
    
    if args.sync:
        print("Syncing with network...")
        success = node.sync_manager.sync_with_network()
        print(f"Sync {'successful' if success else 'failed'}")
        return
    
    if args.discover:
        print("Discovering tasks...")
        node._discover_tasks()
        return
    
    # Start the node
    node.start_time = time.time()
    node.start()


if __name__ == "__main__":
    main()
