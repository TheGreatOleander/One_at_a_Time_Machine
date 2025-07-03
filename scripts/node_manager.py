#!/usr/bin/env python3
"""
Node Manager - Decentralized coordination for One-at-a-Time Machine
Handles task claiming, heartbeats, and inter-node communication
"""

import json
import time
import uuid
import hashlib
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import psutil
import os

class NodeManager:
    def __init__(self, config_path="swarm_config.json"):
        self.config = self.load_config(config_path)
        self.device_id = self.generate_device_id()
        self.ledger_path = Path("ledger.json")
        self.lock_path = Path("ledger.lock")
        self.sync_engine = SyncEngine(self.config)
        self.current_task = None
        self.last_heartbeat = None
        
        # Ensure ledger exists
        self.initialize_ledger()
        
    def load_config(self, config_path: str) -> Dict:
        """Load swarm configuration"""
        default_config = {
            "sync_method": "git",
            "git_repo": "",
            "rclone_remote": "",
            "syncthing_folder": "",
            "heartbeat_interval": 30,
            "task_timeout": 600,
            "min_battery_threshold": 20,
            "max_concurrent_tasks": 1
        }
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return {**default_config, **config}
        except FileNotFoundError:
            print(f"⚠️  Config not found, creating {config_path}")
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def generate_device_id(self) -> str:
        """Generate unique device ID based on hardware"""
        try:
            # Try Android device info first
            result = subprocess.run(['getprop', 'ro.serialno'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                serial = result.stdout.strip()
                return f"android-{hashlib.md5(serial.encode()).hexdigest()[:8]}"
        except:
            pass
        
        # Fallback to MAC address or system info
        try:
            import uuid
            mac = uuid.getnode()
            return f"device-{hex(mac)[2:10]}"
        except:
            return f"node-{uuid.uuid4().hex[:8]}"
    
    def initialize_ledger(self):
        """Create ledger if it doesn't exist"""
        if not self.ledger_path.exists():
            ledger = {
                "queue": [],
                "nodes": [],
                "completed": [],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            self.save_ledger(ledger)
    
    def load_ledger(self) -> Dict:
        """Load ledger with file locking"""
        try:
            with open(self.ledger_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "queue": [],
                "nodes": [],
                "completed": [],
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
    
    def save_ledger(self, ledger: Dict):
        """Save ledger with atomic write"""
        temp_path = self.ledger_path.with_suffix('.tmp')
        ledger["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        with open(temp_path, 'w') as f:
            json.dump(ledger, f, indent=2)
        
        # Atomic rename
        temp_path.replace(self.ledger_path)
    
    def get_battery_level(self) -> int:
        """Get device battery level"""
        try:
            # Android battery info
            result = subprocess.run(['dumpsys', 'battery'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'level:' in line:
                        return int(line.split(':')[1].strip())
        except:
            pass
        
        # Fallback to system battery
        try:
            battery = psutil.sensors_battery()
            if battery:
                return int(battery.percent)
        except:
            pass
        
        return 100  # Default if can't detect
    
    def get_capabilities(self) -> List[str]:
        """Detect device capabilities"""
        caps = []
        
        # Check for programming languages
        try:
            subprocess.run(['python3', '--version'], 
                          capture_output=True, check=True)
            caps.append('python')
        except:
            pass
        
        try:
            subprocess.run(['node', '--version'], 
                          capture_output=True, check=True)
            caps.append('javascript')
        except:
            pass
        
        try:
            subprocess.run(['java', '-version'], 
                          capture_output=True, check=True)
            caps.append('java')
        except:
            pass
        
        # Check platform
        if 'ANDROID_DATA' in os.environ:
            caps.append('android')
        elif os.name == 'nt':
            caps.append('windows')
        else:
            caps.append('linux')
        
        return caps
    
    def heartbeat(self):
        """Send heartbeat and update node status"""
        try:
            # Sync before updating
            self.sync_engine.pull_ledger()
            
            ledger = self.load_ledger()
            
            # Clean up old heartbeats (older than 5 minutes)
            cutoff = datetime.now(timezone.utc).timestamp() - 300
            ledger["nodes"] = [
                node for node in ledger["nodes"] 
                if datetime.fromisoformat(node["last_seen"].replace('Z', '+00:00')).timestamp() > cutoff
            ]
            
            # Update this node's status
            node_info = {
                "device_id": self.device_id,
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "battery": self.get_battery_level(),
                "current_task": self.current_task,
                "capabilities": self.get_capabilities()
            }
            
            # Remove old entry for this device
            ledger["nodes"] = [n for n in ledger["nodes"] if n["device_id"] != self.device_id]
            ledger["nodes"].append(node_info)
            
            # Check for abandoned tasks
            self.cleanup_abandoned_tasks(ledger)
            
            self.save_ledger(ledger)
            self.sync_engine.push_ledger()
            
            self.last_heartbeat = datetime.now(timezone.utc)
            print(f"💓 Heartbeat sent - Battery: {node_info['battery']}%")
            
        except Exception as e:
            print(f"❌ Heartbeat failed: {e}")
    
    def cleanup_abandoned_tasks(self, ledger: Dict):
        """Reset tasks that have been claimed but abandoned"""
        timeout_seconds = self.config["task_timeout"]
        now = datetime.now(timezone.utc).timestamp()
        
        for task in ledger["queue"]:
            if task["status"] == "claimed" and task["claimed_at"]:
                claimed_time = datetime.fromisoformat(task["claimed_at"].replace('Z', '+00:00')).timestamp()
                
                # Check if claiming node is still alive
                claiming_node = next((n for n in ledger["nodes"] if n["device_id"] == task["claimed_by"]), None)
                
                if not claiming_node or (now - claimed_time) > timeout_seconds:
                    print(f"🔄 Releasing abandoned task: {task['title']}")
                    task["status"] = "available"
                    task["claimed_by"] = None
                    task["claimed_at"] = None
    
    def claim_next_task(self) -> Optional[Dict]:
        """Claim the highest priority available task"""
        try:
            # Check battery level
            battery = self.get_battery_level()
            if battery < self.config["min_battery_threshold"]:
                print(f"🔋 Battery too low ({battery}%), skipping tasks")
                return None
            
            self.sync_engine.pull_ledger()
            ledger = self.load_ledger()
            
            # Find highest priority available task
            available_tasks = [
                task for task in ledger["queue"] 
                if task["status"] == "available"
            ]
            
            if not available_tasks:
                return None
            
            # Sort by priority (highest first)
            available_tasks.sort(key=lambda t: t.get("priority", 0), reverse=True)
            task = available_tasks[0]
            
            # Claim the task
            task["status"] = "claimed"
            task["claimed_by"] = self.device_id
            task["claimed_at"] = datetime.now(timezone.utc).isoformat()
            
            self.current_task = task["id"]
            self.save_ledger(ledger)
            self.sync_engine.push_ledger()
            
            print(f"🎯 Claimed task: {task['title']} (Priority: {task.get('priority', 0)})")
            return task
            
        except Exception as e:
            print(f"❌ Failed to claim task: {e}")
            return None
    
    def complete_task(self, task_id: str, solution_path: str):
        """Mark task as completed"""
        try:
            self.sync_engine.pull_ledger()
            ledger = self.load_ledger()
            
            # Find and remove task from queue
            task = None
            for i, t in enumerate(ledger["queue"]):
                if t["id"] == task_id:
                    task = ledger["queue"].pop(i)
                    break
            
            if task:
                # Add to completed
                completed_task = {
                    "id": task_id,
                    "title": task["title"],
                    "completed_by": self.device_id,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "solution_path": solution_path,
                    "priority": task.get("priority", 0)
                }
                ledger["completed"].append(completed_task)
                
                self.current_task = None
                self.save_ledger(ledger)
                self.sync_engine.push_ledger()
                
                print(f"✅ Completed task: {task['title']}")
            else:
                print(f"⚠️  Task {task_id} not found in queue")
                
        except Exception as e:
            print(f"❌ Failed to complete task: {e}")
    
    def add_task(self, task: Dict):
        """Add new task to queue"""
        try:
            self.sync_engine.pull_ledger()
            ledger = self.load_ledger()
            
            # Check if task already exists
            if any(t["id"] == task["id"] for t in ledger["queue"]):
                print(f"⚠️  Task {task['id']} already exists")
                return
            
            task["status"] = "available"
            task["claimed_by"] = None
            task["claimed_at"] = None
            
            ledger["queue"].append(task)
            self.save_ledger(ledger)
            self.sync_engine.push_ledger()
            
            print(f"➕ Added task: {task['title']}")
            
        except Exception as e:
            print(f"❌ Failed to add task: {e}")
    
    def get_status(self) -> Dict:
        """Get current swarm status"""
        try:
            self.sync_engine.pull_ledger()
            ledger = self.load_ledger()
            
            return {
                "device_id": self.device_id,
                "current_task": self.current_task,
                "queue_size": len(ledger["queue"]),
                "active_nodes": len(ledger["nodes"]),
                "completed_tasks": len(ledger["completed"]),
                "battery": self.get_battery_level(),
                "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None
            }
            
        except Exception as e:
            print(f"❌ Failed to get status: {e}")
            return {}

class SyncEngine:
    """Handles synchronization between nodes"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.sync_method = config["sync_method"]
        
    def pull_ledger(self):
        """Pull latest ledger from remote"""
        if self.sync_method == "git":
            self._git_pull()
        elif self.sync_method == "rclone":
            self._rclone_pull()
        elif self.sync_method == "syncthing":
            pass  # Syncthing handles this automatically
    
    def push_ledger(self):
        """Push ledger changes to remote"""
        if self.sync_method == "git":
            self._git_push()
        elif self.sync_method == "rclone":
            self._rclone_push()
        elif self.sync_method == "syncthing":
            pass  # Syncthing handles this automatically
    
    def _git_pull(self):
        """Pull from git repo"""
        try:
            subprocess.run(['git', 'pull'], 
                          capture_output=True, check=True)
        except subprocess.CalledProcessError:
            pass  # Ignore pull errors
    
    def _git_push(self):
        """Push to git repo"""
        try:
            subprocess.run(['git', 'add', 'ledger.json'], 
                          capture_output=True, check=True)
            subprocess.run(['git', 'commit', '-m', f'Update from {self.config.get("device_id", "unknown")}'], 
                          capture_output=True)
            subprocess.run(['git', 'push'], 
                          capture_output=True, check=True)
        except subprocess.CalledProcessError:
            pass  # Ignore push errors
    
    def _rclone_pull(self):
        """Pull from rclone remote"""
        try:
            remote = self.config["rclone_remote"]
            subprocess.run(['rclone', 'copy', f'{remote}ledger.json', '.'], 
                          capture_output=True, check=True)
        except subprocess.CalledProcessError:
            pass
    
    def _rclone_push(self):
        """Push to rclone remote"""
        try:
            remote = self.config["rclone_remote"]
            subprocess.run(['rclone', 'copy', 'ledger.json', remote], 
                          capture_output=True, check=True)
        except subprocess.CalledProcessError:
            pass

# Example usage
if __name__ == "__main__":
    manager = NodeManager()
    
    # Example task
    example_task = {
        "id": "gh-issue-12345",
        "repo": "example/repo",
        "title": "Fix memory leak in core module",
        "description": "Memory usage grows over time...",
        "priority": 85,
        "labels": ["bug", "performance"],
        "url": "https://github.com/example/repo/issues/12345"
    }
    
    # Add task and start heartbeat
    manager.add_task(example_task)
    
    # Heartbeat loop
    while True:
        manager.heartbeat()
        
        # Try to claim a task
        task = manager.claim_next_task()
        if task:
            print(f"🔧 Working on: {task['title']}")
            # Simulate work
            time.sleep(10)
            manager.complete_task(task["id"], f"solutions/{task['id']}/")
        
        time.sleep(manager.config["heartbeat_interval"])
