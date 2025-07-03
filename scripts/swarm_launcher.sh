#!/bin/bash

# One-at-a-Time Machine Swarm Launcher
# Initializes and starts a node in the decentralized swarm

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🤖 One-at-a-Time Machine - Swarm Node Launcher"
echo "==============================================="

# Check if running on Android
if [ -n "$ANDROID_DATA" ]; then
    echo "📱 Android device detected"
    PYTHON_CMD="python"
else
    echo "💻 Desktop/server device detected"
    PYTHON_CMD="python3"
fi

# Check Python availability
if ! command -v $PYTHON_CMD &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.6+"
    exit 1
fi

# Install required packages
echo "📦 Installing dependencies..."
$PYTHON_CMD -m pip install --user --quiet psutil

# Initialize git repo if using git sync
if [ -f "swarm_config.json" ]; then
    SYNC_METHOD=$(python3 -c "import json; print(json.load(open('swarm_config.json'))['sync_method'])" 2>/dev/null || echo "git")
else
    SYNC_METHOD="git"
fi

if [ "$SYNC_METHOD" = "git" ]; then
    if [ ! -d ".git" ]; then
        echo "🔗 Initializing git repository..."
        git init
        git config user.email "node@oatm.local"
        git config user.name "OATM Node"
        
        # Create initial commit
        if [ ! -f "README.md" ]; then
            echo "# One-at-a-Time Machine Ledger" > README.md
            echo "Shared ledger for decentralized task coordination" >> README.md
        fi
        
        git add README.md
        git commit -m "Initial commit"
        
        echo "⚠️  Configure git remote in swarm_config.json"
    fi
fi

# Create config if it doesn't exist
if [ ! -f "swarm_config.json" ]; then
    echo "⚙️  Creating default configuration..."
    cat > swarm_config.json << EOF
{
  "sync_method": "git",
  "git_repo": "",
  "rclone_remote": "gdrive:machine-ledger/",
  "syncthing_folder": "/sdcard/machine-ledger/",
  "heartbeat_interval": 30,
  "task_timeout": 600,
  "min_battery_threshold": 20,
  "max_concurrent_tasks": 1
}
EOF
    echo "📝 Edit swarm_config.json to configure sync method"
fi

# Create systemd service for Linux
create_systemd_service() {
    SERVICE_FILE="$HOME/.local/share/systemd/user/oatm-node.service"
    mkdir -p "$(dirname "$SERVICE_FILE")"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=One-at-a-Time Machine Node
After=network.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_CMD node_manager.py
Restart=always
RestartSec=10
Environment=PATH=$PATH

[Install]
WantedBy=default.target
EOF
    
    systemctl --user daemon-reload
    systemctl --user enable oatm-node.service
    
    echo "🔧 Systemd service created: $SERVICE_FILE"
    echo "   Start with: systemctl --user start oatm-node"
    echo "   Status: systemctl --user status oatm-node"
}

# Create Android service wrapper
create_android_service() {
    cat > start_node.sh << 'EOF'
#!/system/bin/sh

# Android service wrapper
cd /data/local/tmp/oatm
export PATH=/data/local/tmp/oatm:$PATH

# Keep running
while true; do
    python node_manager.py
    echo "Node crashed, restarting in 10 seconds..."
    sleep 10
done
EOF
    
    chmod +x start_node.sh
    echo "📱 Android service script created: start_node.sh"
}

# Platform-specific setup
if [ -n "$ANDROID_DATA" ]; then
    create_android_service
else
    if command -v systemctl &> /dev/null; then
        read -p "Create systemd service? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            create_systemd_service
        fi
    fi
fi

# Check device capabilities
echo "🔍 Detecting device capabilities..."
CAPS=""
if command -v python3 &> /dev/null; then
    CAPS="$CAPS python"
fi
if command -v node &> /dev/null; then
    CAPS="$CAPS javascript"
fi
if command -v java &> /dev/null; then
    CAPS="$CAPS java"
fi

echo "✅ Device capabilities:$CAPS"

# Display device info
echo "📊 Device Information:"
echo "   ID: $(python3 -c "
import hashlib
try:
    import subprocess
    result = subprocess.run(['getprop', 'ro.serialno'], capture_output=True, text=True)
    if result.returncode == 0:
        serial = result.stdout.strip()
        print(f'android-{hashlib.md5(serial.encode()).hexdigest()[:8]}')
    else:
        raise Exception()
except:
    import uuid
    try:
        mac = uuid.getnode()
        print(f'device-{hex(mac)[2:10]}')
    except:
        print(f'node-{uuid.uuid4().hex[:8]}')
")"

# Get battery level
BATTERY="Unknown"
if [ -n "$ANDROID_DATA" ]; then
    BATTERY=$(dumpsys battery 2>/dev/null | grep "level:" | cut -d: -f2 | tr -d ' ' || echo "Unknown")
fi

echo "   Battery: $BATTERY"
echo "   Sync: $SYNC_METHOD"

echo ""
echo "🚀 Ready to launch!"
echo ""
echo "Manual start: $PYTHON_CMD node_manager.py"
echo "Or use the service scripts created above"
echo ""
echo "📡 The swarm awaits your node..."

# Quick test
echo "🧪 Testing node manager..."
timeout 5 $PYTHON_CMD -c "
from node_manager import NodeManager
nm = NodeManager()
print(f'✅ Node manager initialized: {nm.device_id}')
status = nm.get_status()
print(f'✅ Status check passed: {status}')
" || echo "⚠️  Test failed, but node should still work"

echo ""
echo "🔗 Join the swarm by running:"
echo "   $PYTHON_CMD node_manager.py"
