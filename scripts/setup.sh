#!/bin/bash

# One-at-a-Time Machine: Node Setup Script
# Sets up a new node in the swarm

set -e

# Configuration
REPO_URL="https://github.com/TheGreatOleander/One_at_a_Time_Machine.git"
INSTALL_DIR="$HOME/otatm"
CONFIG_FILE="$INSTALL_DIR/config.json"
SERVICE_NAME="otatm"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

detect_platform() {
    if [ -n "$TERMUX_VERSION" ]; then
        echo "termux"
    elif [ "$(uname)" = "Darwin" ]; then
        echo "macos"
    elif [ "$(uname)" = "Linux" ]; then
        if command -v apt-get >/dev/null 2>&1; then
            echo "ubuntu"
        elif command -v yum >/dev/null 2>&1; then
            echo "rhel"
        elif command -v pacman >/dev/null 2>&1; then
            echo "arch"
        else
            echo "linux"
        fi
    else
        echo "unknown"
    fi
}

install_dependencies() {
    local platform=$(detect_platform)
    
    log_info "Installing dependencies for $platform..."
    
    case $platform in
        "termux")
            pkg update && pkg upgrade -y
            pkg install -y python git openssh rclone
            pip install --upgrade pip
            pip install requests
            ;;
        "ubuntu")
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip git curl rclone
            pip3 install --upgrade pip
            pip3 install requests
            ;;
        "rhel")
            sudo yum install -y python3 python3-pip git curl
            pip3 install --upgrade pip
            pip3 install requests
            ;;
        "arch")
            sudo pacman -Sy python python-pip git curl rclone
            pip install --upgrade pip
            pip install requests
            ;;
        "macos")
            if ! command -v brew >/dev/null 2>&1; then
                log_info "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            brew install python3 git rclone
            pip3 install --upgrade pip
            pip3 install requests
            ;;
        *)
            log_error "Unsupported platform: $platform"
            exit 1
            ;;
    esac
}

setup_directory() {
    log_info "Setting up installation directory..."
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warning "Directory $INSTALL_DIR already exists"
        read -p "Remove existing installation? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            log_error "Installation cancelled"
            exit 1
        fi
    fi
    
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"
}

clone_repository() {
    log_info "Cloning repository..."
    
    if [ -d ".git" ]; then
        git pull origin main
    else
        git clone "$REPO_URL" .
    fi
}

setup_configuration() {
    log_info "Setting up configuration..."
    
    if [ ! -f "$CONFIG_FILE" ]; then
        # Create default configuration
        cat > "$CONFIG_FILE" << EOF
{
  "sync_method": "git",
  "ledger_path": "sync/ledger.json",
  "heartbeat_interval": 300,
  "cleanup_interval": 3600,
  "node_timeout_hours": 24,
  "low_battery_threshold": 20,
  "low_battery_multiplier": 3,
  
  "git_repo": "origin",
  "git_branch": "main",
  "git_auto_setup": true,
  
  "github_scan": {
    "enabled": true,
    "languages": ["python", "javascript"],
    "min_stars": 10,
    "max_age_days": 365,
    "labels": ["good first issue", "help wanted"],
    "rate_limit_delay": 1
  },
  
  "scoring": {
    "weights": {
      "stars": 0.3,
      "activity": 0.2,
      "complexity": 0.2,
      "impact": 0.3
    },
    "min_score": 0.5,
    "max_queue_size": 100
  },
  
  "resources": {
    "max_cpu_percent": 80,
    "max_memory_mb": 1024,
    "max_disk_mb": 500,
    "work_directory": "work",
    "temp_directory": "temp"
  }
}
EOF
    fi
    
    # Create sync directory
    mkdir -p sync work temp
}

setup_git() {
    log_info "Setting up Git configuration..."
    
    # Check if git is configured
    if ! git config --global user.name >/dev/null 2>&1; then
        read -p "Enter your Git name: " git_name
        git config --global user.name "$git_name"
    fi
    
    if ! git config --global user.email >/dev/null 2>&1; then
        read -p "Enter your Git email: " git_email
        git config --global user.email "$git_email"
    fi
    
    # Set up GitHub token if needed
    if [ -z "$GITHUB_TOKEN" ]; then
        log_warning "GitHub token not set. Some features may be limited."
        echo "To set up GitHub token:"
        echo "1. Go to https://github.com/settings/tokens"
        echo "2. Generate a new token with 'repo' scope"
        echo "3. Export GITHUB_TOKEN=your_token_here"
        echo "4. Add it to your shell profile for persistence"
    fi
}

create_service() {
    local platform=$(detect_platform)
    
    log_info "Creating system service..."
    
    case $platform in
        "termux")
            # Create Termux service
            mkdir -p ~/.termux/boot
            cat > ~/.termux/boot/otatm << EOF
#!/data/data/com.termux/files/usr/bin/bash
cd $INSTALL_DIR
python3 orchestrator.py --config config.json
EOF
            chmod +x ~/.termux/boot/otatm
            ;;
        "ubuntu"|"rhel"|"arch")
            # Create systemd service
            cat > /tmp/otatm.service << EOF
[Unit]
Description=One-at-a-Time Machine Node
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 orchestrator.py --config config.json
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
            sudo mv /tmp/otatm.service /etc/systemd/system/
            sudo systemctl daemon-reload
            sudo systemctl enable otatm
            ;;
        "macos")
            # Create LaunchAgent
            mkdir -p ~/Library/LaunchAgents
            cat > ~/Library/LaunchAgents/com.otatm.node.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.otatm.node</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>orchestrator.py</string>
        <string>--config</string>
        <string>config.json</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$INSTALL_DIR</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF
            launchctl load ~/Library/LaunchAgents/com.otatm.node.plist
            ;;
    esac
}

setup_environment() {
    log_info "Setting up environment..."
    
    # Create convenience scripts
    cat > otatm-start << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 orchestrator.py --config config.json
EOF
    chmod +x otatm-start
    
    cat > otatm-status << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 heartbeat.py --health
EOF
    chmod +x otatm-status
    
    cat > otatm-swarm << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
python3 heartbeat.py --swarm-health
EOF
    chmod +x otatm-swarm
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        echo "export PATH=\$PATH:$INSTALL_DIR" >> ~/.bashrc
        echo "export PATH=\$PATH:$INSTALL_DIR" >> ~/.profile
    fi
}

test_installation() {
    log_info "Testing installation..."
    
    # Test Python imports
    if ! python3 -c "import requests, json, time, threading" 2>/dev/null; then
        log_error "Python dependencies not properly installed"
        exit 1
    fi
    
    # Test basic functionality
    if ! python3 -c "from sync_manager import SyncManager; sm = SyncManager(); print('SyncManager OK')" 2>/dev/null; then
        log_error "SyncManager not working properly"
        exit 1
    fi
    
    log_success "Installation test passed"
}

main() {
    log_info "Starting One-at-a-Time Machine setup..."
    
    # Check if running as root (not recommended)
    if [ "$EUID" -eq 0 ]; then
        log_warning "Running as root is not recommended"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Setup process
    install_dependencies
    setup_directory
    clone_repository
    setup_configuration
    setup_git
    setup_environment
    test_installation
    
    # Optional service setup
    read -p "Create system service to run automatically? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_service
    fi
    
    log_success "Setup complete!"
    echo
    echo "Next steps:"
    echo "1. Review configuration in $CONFIG_FILE"
    echo "2. Set up GitHub token (if not already done)"
    echo "3. Run: cd $INSTALL_DIR && ./otatm-start"
    echo "4. Check status: ./otatm-status"
    echo "5. View swarm: ./otatm-swarm"
    echo
    echo "Join the swarm and help solve the world's problems, one idea at a time!"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "One-at-a-Time Machine Setup Script"
        echo "Usage: $0 [--help|--uninstall]"
        echo "       $0           # Install/update"
        echo "       $0 --help    # Show this help"
        echo "       $0 --uninstall # Remove installation"
        exit 0
        ;;
    --uninstall)
        log_info "Uninstalling One-at-a-Time Machine..."
        
        # Stop service
        local platform=$(detect_platform)
        case $platform in
            "ubuntu"|"rhel"|"arch")
                sudo systemctl stop otatm 2>/dev/null || true
                sudo systemctl disable otatm 2>/dev/null || true
                sudo rm -f /etc/systemd/system/otatm.service
                sudo systemctl daemon-reload
                ;;
            "macos")
                launchctl unload ~/Library/LaunchAgents/com.otatm.node.plist 2>/dev/null || true
                rm -f ~/Library/LaunchAgents/com.otatm.node.plist
                ;;
            "termux")
                rm -f ~/.termux/boot/otatm
                ;;
        esac
        
        # Remove installation
        rm -rf "$INSTALL_DIR"
        
        log_success "Uninstallation complete"
        exit 0
        ;;
    *)
        main
        ;;
esac
