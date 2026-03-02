# Remote Server Deployment Guide

Deploy Home Network Guardian to a remote server for centralized network monitoring.

## Deployment Scenarios

### Scenario 1: Remote Monitoring Hub (Recommended)
Deploy on a server **within your home network** (e.g., NAS, Raspberry Pi, spare computer):
- Monitors your local network 24/7
- Can send alerts to your phone/email
- No internet connectivity needed for basic operation
- Best for always-on monitoring

### Scenario 2: Cloud-Based Monitoring
Deploy on a VPS/cloud server with network access:
- Requires remote network access to your router
- Monitor from anywhere
- More complex setup (VPN tunnel needed)
- Good for remote network monitoring

### Scenario 3: Multi-Network Monitoring
Deploy multiple instances for different networks:
- Separate instance per network
- Centralized alert aggregation
- Requires network connectivity between servers

---

## Prerequisites for Remote Server

### Minimum Requirements
- Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+) or macOS
- Python 3.8+
- 512MB RAM minimum (1GB+ recommended)
- Network access to target network
- SSH access for setup

### Network Requirements
- **For local network monitoring**: Server must be on the same network
- **For remote monitoring**: VPN tunnel or SSH port forwarding to target network
- Outbound port 25/587 (email) and/or 443 (Telegram)

---

## Quick Deployment Steps

### 1. Prepare Remote Server

SSH into your remote server:
```bash
ssh user@sammy.local
# or
ssh user@sammy_ip_address
```

### 2. Install Dependencies

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Python and required packages
sudo apt-get install -y python3 python3-pip python3-venv git

# For Scapy on Linux (network scanning)
sudo apt-get install -y libpcap-dev

# Optional: for running as service
sudo apt-get install -y supervisor
```

### 3. Clone/Copy Project

Option A: Clone from git (if you have a repo)
```bash
git clone <your-repo> home-network-security
cd home-network-security
```

Option B: Copy from local machine
```bash
# On your local machine:
scp -r home-network-security user@sammy:/home/user/

# Then on remote:
cd /home/user/home-network-security
```

### 4. Set Up Virtual Environment

```bash
cd home-network-security
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure for Remote Environment

Edit `.env` for your remote setup:
```bash
nano .env
```

**Important settings for remote:**
```
# Network monitoring (adjust for your remote network)
NETWORK_INTERFACE=eth0              # Linux interface (check: ip addr)
ROUTER_IP=192.168.1.1              # Target router IP
ROUTER_USERNAME=admin
ROUTER_PASSWORD=your_password

# Notifications (alerts go to your email/phone)
NOTIFICATION_EMAIL=your-email@gmail.com
NOTIFICATION_EMAIL_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id

# Database path (use absolute path on server)
DATABASE_PATH=/home/user/home-network-security/data/network.db
LOG_PATH=/home/user/home-network-security/logs

# Daemon mode
ENABLE_DAEMON_MODE=true
DAEMON_CHECK_INTERVAL=300
```

### 6. Initialize

```bash
python guardian.py init
```

### 7. Scan Network

```bash
python guardian.py scan
```

### 8. Test Alerts

```bash
# Verify email alerts work
python guardian.py setup  # Optional: reconfigure
```

---

## Running as a Service

### Option A: Systemd Service (Recommended for Linux)

Create `/etc/systemd/system/guardian.service`:

```bash
sudo nano /etc/systemd/system/guardian.service
```

Paste:
```ini
[Unit]
Description=Home Network Guardian
After=network.target

[Service]
Type=simple
User=guardian
WorkingDirectory=/home/guardian/home-network-security
ExecStart=/home/guardian/home-network-security/venv/bin/python guardian.py daemon
Restart=on-failure
RestartSec=10

Environment="PATH=/home/guardian/home-network-security/venv/bin"
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable guardian
sudo systemctl start guardian
sudo systemctl status guardian
```

View logs:
```bash
sudo journalctl -u guardian -f
```

### Option B: Supervisor (Alternative)

Create `/etc/supervisor/conf.d/guardian.conf`:

```ini
[program:guardian]
command=/home/user/home-network-security/venv/bin/python /home/user/home-network-security/guardian.py daemon
directory=/home/user/home-network-security
user=user
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/guardian.log
```

Control:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start guardian
sudo supervisorctl status
```

---

## Monitoring Remote Instance

### Check Service Status
```bash
# Via SSH
ssh user@sammy "cd home-network-security && source venv/bin/activate && python guardian.py status"
```

### Create Management Script

Save as `manage_remote.sh`:
```bash
#!/bin/bash

SERVER="user@sammy"
ACTION=${1:-status}

case $ACTION in
    status)
        ssh $SERVER "cd home-network-security && \
                     source venv/bin/activate && \
                     python guardian.py status"
        ;;
    devices)
        ssh $SERVER "cd home-network-security && \
                     source venv/bin/activate && \
                     python guardian.py devices"
        ;;
    alerts)
        ssh $SERVER "cd home-network-security && \
                     source venv/bin/activate && \
                     python guardian.py alerts"
        ;;
    restart)
        ssh $SERVER "sudo systemctl restart guardian"
        ;;
    logs)
        ssh $SERVER "sudo journalctl -u guardian -f"
        ;;
    *)
        echo "Usage: $0 {status|devices|alerts|restart|logs}"
        ;;
esac
```

Use it:
```bash
chmod +x manage_remote.sh
./manage_remote.sh status
./manage_remote.sh alerts
```

---

## Security for Remote Deployment

### 1. SSH Key Authentication
```bash
# Use keys instead of passwords
ssh-copy-id user@sammy

# Disable password auth
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart ssh
```

### 2. Separate User Account
```bash
# Create dedicated user
sudo useradd -m -s /bin/bash guardian
```

### 3. Credential Security
```bash
# Secure .env file
sudo chown guardian:guardian .env
sudo chmod 600 .env
```

### 4. Regular Updates
```bash
# Enable automatic security updates
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Troubleshooting

### Network Interface Not Found

```bash
# List available interfaces
ip addr

# Common: eth0, wlan0, vlan0
# Update .env with correct interface
```

### Can't Reach Router

```bash
# Test connectivity
ping 192.168.1.1

# Check routing
ip route

# Test port
nc -zv 192.168.1.1 80
```

### Service Won't Start

```bash
# Check errors
sudo systemctl status guardian
sudo journalctl -u guardian -n 20

# Manual test
cd home-network-security && source venv/bin/activate
python guardian.py daemon
```

---

For complete information, see [README.md](README.md), [QUICKSTART.md](QUICKSTART.md), and [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md).
