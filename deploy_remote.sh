#!/bin/bash

# Home Network Guardian - Remote Deployment Script
# Usage: ./deploy_remote.sh user@server [remote_path]

set -euo pipefail

SERVER=${1:-}
REMOTE_PATH_INPUT=${2:-home-network-guardian}

if [ -z "$SERVER" ]; then
    echo "❌ Usage: $0 user@server [remote_path]"
    echo ""
    echo "Examples:"
    echo "  ./deploy_remote.sh user@sammy"
    echo "  ./deploy_remote.sh user@sammy /opt/home-network-guardian"
    exit 1
fi

# Resolve remote HOME and final deployment path
REMOTE_HOME=$(ssh "$SERVER" 'printf "%s" "$HOME"')
if [[ "$REMOTE_PATH_INPUT" = /* ]]; then
    REMOTE_PATH="$REMOTE_PATH_INPUT"
else
    REMOTE_PATH="$REMOTE_HOME/$REMOTE_PATH_INPUT"
fi

echo "🚀 Home Network Guardian - Remote Deployment"
echo "================================================"
echo ""
echo "📍 Target Server: $SERVER"
echo "📁 Remote Path: $REMOTE_PATH"
echo ""

# Step 1: Copy project
echo "1️⃣  Copying project files..."
ssh "$SERVER" "mkdir -p '$REMOTE_PATH'"

# Copy project contents while excluding local-only/cache folders
tar --no-xattrs \
    --exclude='./venv' \
    --exclude='./.venv' \
    --exclude='./__pycache__' \
    --exclude='./.git' \
    --exclude='./.pytest_cache' \
    -czf - . | ssh "$SERVER" "tar -xzf - -C '$REMOTE_PATH'" || {
    echo "❌ Failed to copy files"
    exit 1
}
echo "✅ Files copied"
echo ""

# Step 2: Setup on remote
echo "2️⃣  Setting up remote environment..."
ssh "$SERVER" bash -s -- "$REMOTE_PATH" << 'REMOTE_SETUP'
    set -e

    # Remote path passed as first arg
    REMOTE_PATH="$1"

    cd $REMOTE_PATH

    can_sudo_nopass=false
    if command -v sudo &> /dev/null && sudo -n true 2>/dev/null; then
        can_sudo_nopass=true
    fi

    # Install Python dependencies (if not already installed)
    if ! command -v python3 &> /dev/null; then
        if command -v apt-get &> /dev/null; then
            if [ "$can_sudo_nopass" = true ]; then
                echo "Installing Python..."
                sudo apt-get update
                sudo apt-get install -y python3 python3-pip python3-venv
            else
                echo "❌ python3 is missing and sudo needs a password. Install python3 manually, then rerun."
                exit 1
            fi
        else
            echo "❌ python3 is not installed and apt-get is unavailable. Install python3 manually."
            exit 1
        fi
    fi

    # Install Scapy dependencies
    if command -v apt-get &> /dev/null && command -v dpkg &> /dev/null && ! dpkg -l | grep -q libpcap-dev; then
        if [ "$can_sudo_nopass" = true ]; then
            echo "Installing libpcap..."
            sudo apt-get install -y libpcap-dev
        else
            echo "⚠️  Skipping libpcap-dev install (sudo password required in non-interactive session)."
            echo "   If install fails later, run on server: sudo apt-get install -y libpcap-dev"
        fi
    fi

    # Create virtual environment
    if [ ! -d "venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv venv
    fi

    # Activate and install requirements
    echo "Installing Python packages..."
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel

    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
    elif [ -f "pyproject.toml" ]; then
        pip install -e .
    else
        echo "❌ No requirements.txt or pyproject.toml found in $REMOTE_PATH"
        exit 1
    fi

    # Create necessary directories
    mkdir -p data logs

    echo "✅ Remote setup complete"
REMOTE_SETUP

echo "✅ Environment configured"
echo ""

# Step 3: Initialize database
echo "3️⃣  Initializing database..."
ssh "$SERVER" bash -s -- "$REMOTE_PATH" << 'INIT_DB'
    set -e
    REMOTE_PATH="$1"
    cd $REMOTE_PATH
    source venv/bin/activate

    # Initialize if supported by project layout
    if [ -f "guardian.py" ]; then
        python guardian.py init
        echo "✅ Database initialized via guardian.py init"
    elif command -v hng >/dev/null 2>&1; then
        echo "✅ CLI installed (hng). Skipping forced init to avoid config-dependent failures."
    else
        echo "⚠️  No known init command detected."
    fi
INIT_DB

echo ""

# Step 4: Instructions
echo "4️⃣  Next steps:"
echo ""
echo "SSH into the remote server:"
echo "  ssh $SERVER"
echo ""
echo "Then run setup:"
echo "  cd $REMOTE_PATH"
echo "  source venv/bin/activate"
echo "  cp .env.example .env"
echo "  # edit .env values"
echo "  hng init-baseline"
echo ""
echo "Start monitoring:"
echo "  hng daemon"
echo ""
echo "Or set up as a service (see REMOTE_DEPLOYMENT.md)"
echo ""
echo "✅ Deployment ready!"
