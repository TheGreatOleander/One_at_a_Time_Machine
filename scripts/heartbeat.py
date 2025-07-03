#!/usr/bin/env python3
"""
One-at-a-Time Machine: Heartbeat System
Continuous status reporting and node health monitoring
"""

import time
import threading
import signal
import sys
from datetime import datetime, timezone
from sync_manager import SyncManager

class HeartbeatManager:
    def __init__(self, sync_manager: SyncManager):
        self.sync_manager = sync_manager
        self.running = False
        self.heartbeat_thread = None
        self.cleanup_thread = None
        
        # Intervals in seconds
        self.heartbeat_interval = 300  # 5 minutes
        self.cleanup_interval = 1800   # 30 minutes
        self.idle_heartbeat_interval = 1800  # 30 minutes when idle
        
        # Current status
        self.current_status = "idle"
        self.current_task = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n[HEARTBEAT] Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def start(self):
        """Start the heartbeat system"""
        if self.running:
            return
        
        self.running = True
        print(f"[HEARTBEAT] Starting heartbeat system for device {self.sync_manager.device_id}")
        
        # Start heartbeat thread
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        # Send initial heartbeat
        self._send_heartbeat()
    
    def stop(self):
        """Stop the heartbeat system"""
        if not self.running:
            return
        
        print("[HEARTBEAT] Stopping heartbeat system...")
        self.running = False
        
        # Send final heartbeat with offline status
        self.update_status("offline")
        
        # Wait for threads to finish
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=5)
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        
        print("[HEARTBEAT] Heartbeat system stopped")
    
    def _heartbeat_loop(self):
        """Main heartbeat loop"""
        while self.running:
            try:
                self._send_heartbeat()
                
                # Dynamic interval based on status
                if self.current_status == "idle":
                    interval = self.idle_heartbeat_interval
                else:
                    interval = self.heartbeat_interval
                
                # Sleep with regular checks for shutdown
                for _ in range(interval):
                    if not self.running:
                        break
                    time.sleep(1)
                
            except Exception as e:
                print(f"[HEARTBEAT] Error in heartbeat loop: {e}")
                time.sleep(30)  # Back off on error
    
    def _cleanup_loop(self):
        """Periodic cleanup of stale nodes"""
        while self.running:
            try:
                self.sync_manager.cleanup_stale_nodes()
                
                # Sleep with regular checks for shutdown
                for _ in range(self.cleanup_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                
            except Exception as e:
                print(f"[HEARTBEAT] Error in cleanup loop: {e}")
                time.sleep(60)  # Back off on error
    
    def _send_heartbeat(self):
        """Send heartbeat to the network"""
        try:
            # Update our status in the ledger
            self.sync_manager.update_node_status(self.current_status, self.current_task)
            
            # Sync with network
            success = self.sync_manager.sync_with_network()
            
            if success:
                print(f"[HEARTBEAT] Sent heartbeat - Status: {self.current_status}")
            else:
                print(f"[HEARTBEAT] Failed to sync heartbeat")
                
        except Exception as e:
            print(f"[HEARTBEAT] Error sending heartbeat: {e}")
    
    def update_status(self, status: str, task: str = None):
        """Update node status"""
        self.current_status = status
        self.current_task = task
        
        # Send immediate heartbeat on status change
        self._send_heartbeat()
        
        print(f"[HEARTBEAT] Status updated: {status} - Task: {task}")
    
    def get_network_health(self) -> dict:
        """Get network health metrics"""
        try:
            swarm_status = self.sync_manager.get_swarm_status()
            
            # Calculate health metrics
            total_nodes = swarm_status["total_nodes"]
            active_nodes = swarm_status["active_nodes"]
            
            if total_nodes == 0:
                node_health = 0.0
            else:
                node_health = active_nodes / total_nodes
            
            # Task queue health
            pending = swarm_status["pending_tasks"]
            active = swarm_status["active_tasks"]
            completed = swarm_status["completed_tasks"]
            
            total_tasks = pending + active + completed
            if total_tasks == 0:
                task_progress = 0.0
            else:
                task_progress = completed / total_tasks
            
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "node_health": node_health,
                "task_progress": task_progress,
                "active_nodes": active_nodes,
                "total_nodes": total_nodes,
                "pending_tasks": pending,
                "active_tasks": active,
                "completed_tasks": completed,
                "our_device_id": self.sync_manager.device_id,
                "our_status": self.current_status
            }
            
        except Exception as e:
            print(f"[HEARTBEAT] Error getting network health: {e}")
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e)
            }
    
    def wait_for_network_sync(self, timeout: int = 60) -> bool:
        """Wait for network synchronization"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.sync_manager.sync_with_network():
                return True
            time.sleep(5)
        
        return False


def main():
    """Simple CLI for testing heartbeat system"""
    import sys
    import json
    
    # Initialize sync manager and heartbeat
    sync_manager = SyncManager()
    heartbeat = HeartbeatManager(sync_manager)
    
    if len(sys.argv) < 2:
        print("Usage: python heartbeat.py [start|status|health|test]")
        return
    
    command = sys.argv[1]
    
    if command == "start":
        print("Starting heartbeat system...")
        heartbeat.start()
        
        try:
            # Keep running until interrupted
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
            heartbeat.stop()
    
    elif command == "status":
        status = sync_manager.get_swarm_status()
        print(json.dumps(status, indent=2))
    
    elif command == "health":
        health = heartbeat.get_network_health()
        print(json.dumps(health, indent=2))
    
    elif command == "test":
        # Test heartbeat functionality
        heartbeat.start()
        
        print("Testing status updates...")
        heartbeat.update_status("working", "test-task-url")
        time.sleep(2)
        
        heartbeat.update_status("idle")
        time.sleep(2)
        
        print("Network health:")
        health = heartbeat.get_network_health()
        print(json.dumps(health, indent=2))
        
        heartbeat.stop()
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
