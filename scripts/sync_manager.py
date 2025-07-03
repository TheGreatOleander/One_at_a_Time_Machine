#!/usr/bin/env python3
"""
One-at-a-Time Machine: Node Coordination System
Manages the global ledger and task synchronization across devices
"""

import json
import os
import time
import uuid
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

class SyncManager:
    def __init__(self, sync_method="git", sync_config=None):
        self.device_id = self._get_device_id()
        self.sync_method = sync_method
        self.sync_config = sync_config or {}
        self.ledger_path = Path("sync/ledger.json")
        self.ledger_path.parent.mkdir(exist_ok=True)
        
        # Initialize ledger if it doesn't exist
        if not self.ledger_path.exists():
            self._initialize_ledger()
    
    def _get_device_id(self) -> str:
        """Generate consistent device ID based on hardware"""
        try:
            # Try multiple methods to get unique hardware ID
            sources = []
            
            # MAC address
            try:
                import uuid
                sources.append(str(uuid.getnode()))
            except:
                pass
            
            # System info
            try:
                import platform
                sources.append(platform.node())
                sources.append(platform.machine())
            except:
                pass
            
            # Fallback to random UUID stored in file
            device_file = Path("sync/.device_id")
            if device_file.exists():
                sources.append(device_file.read_text().strip())
            else:
                fallback_id = str(uuid.uuid4())
                device_file.write_text(fallback_id)
                sources.append(fallback_id)
            
            # Hash all sources for consistent ID
            combined = "-".join(sources)
            return hashlib.md5(combined.encode()).hexdigest()[:12]
        except:
            return str(uuid.uuid4())[:12]
    
    def _initialize_ledger(self):
        """Create initial ledger structure"""
        ledger = {
            "nodes": {},
            "queue": {
                "pending": [],
                "active": [],
                "completed": []
            },
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        self._write_ledger(ledger)
    
    def _read_ledger(self) -> Dict[str, Any]:
        """Read ledger with error handling"""
        try:
            with open(self.ledger_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"[SYNC] Ledger corrupted or missing, initializing fresh")
            self._initialize_ledger()
            return self._read_ledger()
    
    def _write_ledger(self, ledger: Dict[str, Any]):
        """Write ledger atomically"""
        temp_path = self.ledger_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(ledger, f, indent=2)
        temp_path.replace(self.ledger_path)
    
    def sync_with_network(self) -> bool:
        """Pull latest ledger, merge changes, push updates"""
        try:
            if self.sync_method == "git":
                return self._sync_git()
            elif self.sync_method == "rclone":
                return self._sync_rclone()
            elif self.sync_method == "syncthing":
                return self._sync_syncthing()
            else:
                print(f"[SYNC] Unknown sync method: {self.sync_method}")
                return False
        except Exception as e:
            print(f"[SYNC] Network sync failed: {e}")
            return False
    
    def _sync_git(self) -> bool:
        """Git-based synchronization"""
        try:
            # Pull latest changes
            subprocess.run(["git", "pull"], cwd=".", capture_output=True, check=True)
            
            # Add and commit our changes
            subprocess.run(["git", "add", "sync/ledger.json"], cwd=".", capture_output=True)
            commit_msg = f"Node {self.device_id}: ledger update"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=".", capture_output=True)
            
            # Push with retry
            for attempt in range(3):
                try:
                    subprocess.run(["git", "push"], cwd=".", capture_output=True, check=True)
                    return True
                except subprocess.CalledProcessError:
                    if attempt < 2:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        subprocess.run(["git", "pull"], cwd=".", capture_output=True)
                    else:
                        raise
            return False
        except Exception as e:
            print(f"[SYNC] Git sync failed: {e}")
            return False
    
    def _sync_rclone(self) -> bool:
        """Cloud storage synchronization"""
        remote = self.sync_config.get('remote', 'remote:otatm')
        try:
            # Download latest
            subprocess.run([
                "rclone", "copy", f"{remote}/ledger.json", "sync/"
            ], capture_output=True, check=True)
            
            # Upload our version
            subprocess.run([
                "rclone", "copy", "sync/ledger.json", f"{remote}/"
            ], capture_output=True, check=True)
            
            return True
        except Exception as e:
            print(f"[SYNC] Rclone sync failed: {e}")
            return False
    
    def _sync_syncthing(self) -> bool:
        """Peer-to-peer synchronization (passive)"""
        # Syncthing handles the actual sync, we just update timestamp
        return True
    
    def claim_next_task(self) -> Optional[str]:
        """Atomically claim the next available task"""
        ledger = self._read_ledger()
        
        # Check if we already have an active task
        our_node = ledger["nodes"].get(self.device_id, {})
        if our_node.get("current_task"):
            return our_node["current_task"]
        
        # Find next available task
        if not ledger["queue"]["pending"]:
            return None
        
        # Claim the first pending task
        task_url = ledger["queue"]["pending"].pop(0)
        ledger["queue"]["active"].append(task_url)
        
        # Update our node status
        self.update_node_status_in_ledger(ledger, "working", task_url)
        
        # Save and sync
        self._write_ledger(ledger)
        self.sync_with_network()
        
        print(f"[SYNC] Claimed task: {task_url}")
        return task_url
    
    def complete_task(self, task_url: str):
        """Mark task as completed and claim next"""
        ledger = self._read_ledger()
        
        # Move task from active to completed
        if task_url in ledger["queue"]["active"]:
            ledger["queue"]["active"].remove(task_url)
        ledger["queue"]["completed"].append(task_url)
        
        # Update our node status
        self.update_node_status_in_ledger(ledger, "idle", None)
        
        # Increment completed count
        if self.device_id in ledger["nodes"]:
            ledger["nodes"][self.device_id]["completed_tasks"] = (
                ledger["nodes"][self.device_id].get("completed_tasks", 0) + 1
            )
        
        self._write_ledger(ledger)
        self.sync_with_network()
        
        print(f"[SYNC] Completed task: {task_url}")
    
    def add_tasks_to_queue(self, task_urls: List[str]):
        """Add new tasks to the pending queue"""
        ledger = self._read_ledger()
        
        # Add only new tasks
        for task_url in task_urls:
            if (task_url not in ledger["queue"]["pending"] and
                task_url not in ledger["queue"]["active"] and
                task_url not in ledger["queue"]["completed"]):
                ledger["queue"]["pending"].append(task_url)
        
        self._write_ledger(ledger)
        self.sync_with_network()
        
        print(f"[SYNC] Added {len(task_urls)} tasks to queue")
    
    def update_node_status_in_ledger(self, ledger: Dict[str, Any], status: str, task: Optional[str] = None):
        """Update this node's status in the ledger"""
        if self.device_id not in ledger["nodes"]:
            ledger["nodes"][self.device_id] = {"completed_tasks": 0}
        
        node = ledger["nodes"][self.device_id]
        node.update({
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "battery_level": self._get_battery_level(),
            "status": status,
            "current_task": task
        })
        
        ledger["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    def update_node_status(self, status: str, task: Optional[str] = None):
        """Update this node's status"""
        ledger = self._read_ledger()
        self.update_node_status_in_ledger(ledger, status, task)
        self._write_ledger(ledger)
    
    def _get_battery_level(self) -> int:
        """Get device battery level"""
        try:
            # Android
            result = subprocess.run(
                ["termux-battery-status"], 
                capture_output=True, text=True
            )
            if result.returncode == 0:
                battery_info = json.loads(result.stdout)
                return battery_info.get("percentage", 100)
        except:
            pass
        
        try:
            # Linux
            battery_path = Path("/sys/class/power_supply/BAT0/capacity")
            if battery_path.exists():
                return int(battery_path.read_text().strip())
        except:
            pass
        
        return 100  # Default for devices without battery info
    
    def get_swarm_status(self) -> Dict[str, Any]:
        """Get current swarm status"""
        ledger = self._read_ledger()
        
        # Count active nodes (seen in last 10 minutes)
        now = datetime.now(timezone.utc)
        active_nodes = 0
        
        for node_id, node in ledger["nodes"].items():
            try:
                last_seen = datetime.fromisoformat(node["last_seen"].replace('Z', '+00:00'))
                if (now - last_seen).total_seconds() < 600:  # 10 minutes
                    active_nodes += 1
            except:
                pass
        
        return {
            "active_nodes": active_nodes,
            "total_nodes": len(ledger["nodes"]),
            "pending_tasks": len(ledger["queue"]["pending"]),
            "active_tasks": len(ledger["queue"]["active"]),
            "completed_tasks": len(ledger["queue"]["completed"]),
            "our_device_id": self.device_id
        }
    
    def cleanup_stale_nodes(self):
        """Remove stale nodes and reclaim their tasks"""
        ledger = self._read_ledger()
        now = datetime.now(timezone.utc)
        stale_threshold = 1800  # 30 minutes
        
        stale_nodes = []
        for node_id, node in ledger["nodes"].items():
            try:
                last_seen = datetime.fromisoformat(node["last_seen"].replace('Z', '+00:00'))
                if (now - last_seen).total_seconds() > stale_threshold:
                    stale_nodes.append(node_id)
            except:
                stale_nodes.append(node_id)
        
        # Reclaim tasks from stale nodes
        for node_id in stale_nodes:
            node = ledger["nodes"][node_id]
            if node.get("current_task"):
                task_url = node["current_task"]
                # Move task back to pending
                if task_url in ledger["queue"]["active"]:
                    ledger["queue"]["active"].remove(task_url)
                    ledger["queue"]["pending"].insert(0, task_url)
                print(f"[SYNC] Reclaimed task from stale node {node_id}: {task_url}")
            
            # Remove stale node
            del ledger["nodes"][node_id]
        
        if stale_nodes:
            self._write_ledger(ledger)
            print(f"[SYNC] Cleaned up {len(stale_nodes)} stale nodes")


def main():
    """Simple CLI for testing"""
    import sys
    
    sync_manager = SyncManager()
    
    if len(sys.argv) < 2:
        print("Usage: python sync_manager.py [status|claim|complete|add] [args...]")
        return
    
    command = sys.argv[1]
    
    if command == "status":
        status = sync_manager.get_swarm_status()
        print(json.dumps(status, indent=2))
    
    elif command == "claim":
        task = sync_manager.claim_next_task()
        print(f"Claimed task: {task}")
    
    elif command == "complete":
        if len(sys.argv) < 3:
            print("Usage: python sync_manager.py complete <task_url>")
            return
        sync_manager.complete_task(sys.argv[2])
    
    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: python sync_manager.py add <task_url1> [task_url2...]")
            return
        sync_manager.add_tasks_to_queue(sys.argv[2:])
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
