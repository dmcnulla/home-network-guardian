# 🚀 Running Guardian on Remote Server (Sammy)

Yes! You can absolutely run Home Network Guardian on your remote server **Sammy**. Here's how to do it:

## Quick Summary

✅ **Yes, it runs on remote servers**
- Works on any Linux/macOS server
- Perfect for 24/7 monitoring
- Send alerts to your phone/email
- Automatic daemon mode

---

## Three Ways to Deploy

### Option 1: Automated Deployment (Easiest) ⭐
```bash
./deploy_remote.sh user@sammy
```
This script automates everything!

### Option 2: Manual Deployment (Full Control)
Follow the steps in [REMOTE_DEPLOYMENT.md](REMOTE_DEPLOYMENT.md)

### Option 3: Copy & Run (Simplest)
```bash
# Copy project to server
scp -r . user@sammy:/home/user/

# SSH in and run
ssh user@sammy
cd home-network-security
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python guardian.py setup
python guardian.py daemon
```

---

## What You Get on Remote Server

✅ **Continuous Monitoring**
- Runs 24/7 in background
- Scans network every 5 minutes
- Checks credentials periodically

✅ **Real-Time Alerts**
- Email notifications to your phone
- Telegram messages
- Historical logs stored on server

✅ **Easy Management**
- SSH in to check status
- View alerts anytime
- Control remotely

---

## Prerequisites for Sammy

Your remote server needs:
- Python 3.8+ (check: `python3 --version`)
- Network access to your home router
- Email/Telegram for alerts (optional)
- SSH access for management

## Quick Setup on Sammy

```bash
# 1. SSH into Sammy
ssh user@sammy

# 2. Install dependencies (first time only)
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv libpcap-dev

# 3. Copy project from your local machine
# Run this on your LOCAL machine:
scp -r /Users/davidj.mcnulla/Projects/home-network-security user@sammy:/home/user/

# 4. Setup on Sammy (back in SSH session)
cd /home/user/home-network-security
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure
python guardian.py setup
python guardian.py init
python guardian.py scan

# 6. Start monitoring
python guardian.py daemon

# Or run as service (see below)
```

---

## Running as a Service (Recommended)

So it starts automatically and runs forever:

### Systemd (Linux)

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
User=user
WorkingDirectory=/home/user/home-network-security
ExecStart=/home/user/home-network-security/venv/bin/python /home/user/home-network-security/guardian.py daemon
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable guardian
sudo systemctl start guardian
sudo systemctl status guardian
```

Check logs:
```bash
sudo journalctl -u guardian -f
```

---

## Manage Remote Instance

### From Your Local Machine

Check status:
```bash
ssh user@sammy "cd home-network-security && source venv/bin/activate && python guardian.py status"
```

View devices:
```bash
ssh user@sammy "cd home-network-security && source venv/bin/activate && python guardian.py devices"
```

View alerts:
```bash
ssh user@sammy "cd home-network-security && source venv/bin/activate && python guardian.py alerts"
```

Restart service:
```bash
ssh user@sammy "sudo systemctl restart guardian"
```

View logs:
```bash
ssh user@sammy "sudo journalctl -u guardian -f"
```

---

## Common Network Configurations

### Local Network (Sammy on same network as router)
```
Your Home Network:
├─ Router (192.168.1.1)
├─ Your Computer
└─ Sammy Server ← Best for monitoring!
```

**Configuration (.env):**
```
NETWORK_INTERFACE=eth0
ROUTER_IP=192.168.1.1
ROUTER_USERNAME=admin
ROUTER_PASSWORD=your_password
```

### Remote Server (VPN needed)

If Sammy is outside your home network, you need to create a tunnel:

```bash
# Option 1: SSH tunnel
ssh -L 2222:192.168.1.1:22 user@vpn_gateway &

# Option 2: WireGuard (better)
# Configure WireGuard connection to your home network
```

Then update .env to use the tunnel address.

---

## Monitoring Multiple Networks

You can run multiple Guardian instances on Sammy:

```bash
/home/user/
├── guardian-home/          # Monitor home network
│   ├── venv/
│   └── .env (192.168.1.1)
└── guardian-office/        # Monitor office network
    ├── venv/
    └── .env (10.0.0.1)
```

Create separate systemd services for each.

---

## Troubleshooting Remote Setup

### SSH Connection Issues
```bash
# Test connection
ssh user@sammy "echo ✅ Connection working"

# Use verbose mode for debugging
ssh -v user@sammy
```

### Network Interface Not Found
```bash
# On Sammy, check available interfaces
ip addr

# Common:
# - eth0, eth1 (Ethernet)
# - wlan0 (WiFi)
# - vlan0 (Virtual LAN)

# Update .env
nano .env  # Set NETWORK_INTERFACE=eth0
```

### Can't Reach Router from Sammy
```bash
# Test connectivity
ping 192.168.1.1

# Check routing
ip route

# If fails: Sammy might not be on same network
# Need VPN tunnel or network configuration
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

## File Transfer Methods

### Option 1: SCP (Simple)
```bash
# One-time copy
scp -r home-network-security user@sammy:/home/user/
```

### Option 2: Git (Better for updates)
```bash
# Setup Git repo first, then on Sammy:
git clone https://your-repo.git home-network-security
cd home-network-security
```

### Option 3: Rsync (For updates)
```bash
# Sync changes
rsync -avz home-network-security/ user@sammy:/home/user/home-network-security/

# Only changed files
rsync -avz --delete home-network-security/ user@sammy:/home/user/home-network-security/
```

---

## Backup on Remote Server

Automatically backup the database:

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/home/user/backups"
PROJECT_DIR="/home/user/home-network-security"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp $PROJECT_DIR/data/network.db $BACKUP_DIR/network_${DATE}.db

# Keep last 30 days
find $BACKUP_DIR -name "network_*.db" -mtime +30 -delete

echo "✅ Backup complete: $DATE"
```

Schedule with cron:
```bash
# Edit crontab
crontab -e

# Add: Daily backup at 2 AM
0 2 * * * /home/user/home-network-security/backup.sh
```

---

## Security Best Practices

✅ Use SSH keys instead of passwords
```bash
ssh-copy-id user@sammy
```

✅ Secure .env file
```bash
sudo chown user:user .env
sudo chmod 600 .env
```

✅ Enable automatic updates
```bash
sudo apt-get install -y unattended-upgrades
```

✅ Use firewall
```bash
sudo ufw enable
sudo ufw allow ssh
```

---

## Cost Estimation

| Option | Cost | Best For |
|--------|------|----------|
| Existing home server | $0 | Always-on monitoring |
| Raspberry Pi | $50-100 | Budget monitoring |
| NAS device | $200-500 | Integrated solution |
| VPS ($5/month) | $60/year | Remote monitoring |

---

## Advantages of Remote Deployment

✅ **24/7 Monitoring**
- Runs continuously while your computer is off

✅ **Centralized Alerts**
- All notifications go to your email/phone
- Accessible from anywhere

✅ **Historical Data**
- Database stored on server
- Review threats later

✅ **Resource Efficient**
- Minimal CPU/memory usage
- Perfect for dedicated hardware

✅ **Always Available**
- Server runs independently
- No local computer needed

---

## Next Steps

1. **Deploy**: 
   ```bash
   ./deploy_remote.sh user@sammy
   ```

2. **Configure**:
   ```bash
   ssh user@sammy
   cd home-network-security
   source venv/bin/activate
   python guardian.py setup
   ```

3. **Initialize**:
   ```bash
   python guardian.py init
   python guardian.py scan
   ```

4. **Run**:
   ```bash
   python guardian.py daemon
   # Or setup as service
   ```

5. **Monitor**:
   ```bash
   python guardian.py status
   python guardian.py alerts
   ```

---

## Support

📖 See [REMOTE_DEPLOYMENT.md](REMOTE_DEPLOYMENT.md) for detailed instructions  
📖 See [README.md](README.md) for complete documentation  
📖 See [QUICKSTART.md](QUICKSTART.md) for initial setup  

---

**Happy remote monitoring!** 🛡️
