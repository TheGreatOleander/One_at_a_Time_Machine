{
  "sync_method": "git",
  "git_repo": "https://github.com/your-username/machine-ledger.git",
  "rclone_remote": "gdrive:machine-ledger/",
  "syncthing_folder": "/sdcard/machine-ledger/",
  "heartbeat_interval": 30,
  "task_timeout": 600,
  "min_battery_threshold": 20,
  "max_concurrent_tasks": 1,
  "node_name": "auto",
  "priority_weights": {
    "bug": 2.0,
    "performance": 1.5,
    "security": 3.0,
    "feature": 1.0
  },
  "ignore_repos": [
    "spam-repo",
    "test-only"
  ],
  "preferred_languages": [
    "python",
    "javascript", 
    "java"
  ]
}
