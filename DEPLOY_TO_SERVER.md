# 🚀 Deploy to api.xoperr.dev with Nginx + Systemd

**Status:** Ready to Deploy
**Domain:** api.xoperr.dev
**Framework:** FastAPI (behind Nginx)
**Process Manager:** Systemd

---

## Step 1: Install System Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Install pip packages with break-system-packages
pip3 install fastapi==0.104.1 uvicorn==0.24.0 python-multipart==0.0.6 \
    httpx==0.25.0 aiofiles==23.2.1 --break-system-packages
```

---

## Step 2: Get SSL Certificate

```bash
sudo certbot certonly --nginx -d api.xoperr.dev

# Or standalone if nginx isn't running yet:
# sudo certbot certonly --standalone -d api.xoperr.dev
```

---

## Step 3: Setup Nginx

Copy the nginx configuration:

```bash
# Copy nginx config
sudo cp /home/xoperr/projects/server/API/nginx.conf \
    /etc/nginx/sites-available/api.xoperr.dev

# Enable the site
sudo ln -s /etc/nginx/sites-available/api.xoperr.dev \
    /etc/nginx/sites-enabled/api.xoperr.dev

# Remove default site if exists
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx config
sudo nginx -t

# Start/restart nginx
sudo systemctl enable nginx
sudo systemctl restart nginx
```

---

## Step 4: Setup Systemd Service

Install the systemd service:

```bash
# First, update the service file with your API key
nano /home/xoperr/projects/server/API/lessons-api.service
# Find: Environment="OPENROUTER_API_KEY=sk_your_api_key_here"
# Replace: sk_your_api_key_here with your actual key

# Copy service file
sudo cp /home/xoperr/projects/server/API/lessons-api.service \
    /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable lessons-api
sudo systemctl start lessons-api

# Verify it's running
sudo systemctl status lessons-api
```

---

## Step 5: Verify Everything Works

```bash
# Check service status
sudo systemctl status lessons-api

# Check nginx status
sudo systemctl status nginx

# Test the API
curl https://api.xoperr.dev/health

# View logs
sudo journalctl -u lessons-api -f

# View nginx logs
sudo tail -f /var/log/nginx/api.xoperr.dev.access.log
sudo tail -f /var/log/nginx/api.xoperr.dev.error.log
```

---

## Architecture Diagram

```
User/Client
    ↓
    ├─ HTTPS (443)
    ↓
Nginx (Reverse Proxy)
    ├─ SSL/TLS termination
    ├─ Load balancing
    ├─ Static caching
    ↓ HTTP (127.0.0.1:5000)
FastAPI (Uvicorn)
    ├─ 2 workers
    ├─ Async I/O
    ├─ Token management
    ↓
Lessons Data & Models
    ├─ lessons.json
    ├─ users.json
    ├─ profiles.json
    └─ Whisper (lazy loaded)
```

---

## Service Management Commands

```bash
# Start the service
sudo systemctl start lessons-api

# Stop the service
sudo systemctl stop lessons-api

# Restart the service
sudo systemctl restart lessons-api

# Check status
sudo systemctl status lessons-api

# View real-time logs
sudo journalctl -u lessons-api -f

# View last 100 lines
sudo journalctl -u lessons-api -n 100

# View logs from last hour
sudo journalctl -u lessons-api --since "1 hour ago"
```

---

## Nginx Management Commands

```bash
# Test configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx

# Reload nginx (without restart)
sudo systemctl reload nginx

# Check status
sudo systemctl status nginx

# View error logs
sudo tail -f /var/log/nginx/api.xoperr.dev.error.log

# View access logs
sudo tail -f /var/log/nginx/api.xoperr.dev.access.log
```

---

## Monitoring & Maintenance

### Check Memory Usage

```bash
# Current memory
free -h

# Memory used by FastAPI
ps aux | grep uvicorn

# Monitor in real-time
watch -n 1 'free -h && echo "---" && ps aux | grep uvicorn | grep -v grep'
```

### Check Disk Space

```bash
df -h
du -sh /home/xoperr/projects/server/API
```

### Renew SSL Certificate

```bash
# Manual renewal
sudo certbot renew

# Auto-renewal (usually runs automatically)
sudo systemctl status certbot.timer
```

### View Service Logs

```bash
# Last 50 lines
sudo journalctl -u lessons-api -n 50

# Watch live
sudo journalctl -u lessons-api -f

# Show errors only
sudo journalctl -u lessons-api -p err
```

---

## Troubleshooting

### Service won't start

```bash
# Check service status
sudo systemctl status lessons-api

# Check for errors
sudo journalctl -u lessons-api -n 50

# Check if port 5000 is in use
sudo lsof -i :5000

# Check if user www-data can access the directory
ls -la /home/xoperr/projects/server/API
```

### Nginx giving 502 Bad Gateway

```bash
# Check if FastAPI is running
sudo systemctl status lessons-api

# Check nginx error log
sudo tail -f /var/log/nginx/api.xoperr.dev.error.log

# Check if port 5000 is listening
sudo ss -tlnp | grep 5000

# Restart both
sudo systemctl restart lessons-api
sudo systemctl restart nginx
```

### High memory usage

```bash
# Check what's consuming memory
ps aux | sort -k6 -n | tail -20

# If Whisper is loaded (high memory):
# - Check STT was called: grep "Loading Whisper" in logs
# - Can restart service to unload: sudo systemctl restart lessons-api

# Check workers
ps aux | grep uvicorn
# Should see: 2 worker processes + 1 master
```

### SSL certificate issues

```bash
# Check certificate status
sudo certbot certificates

# Check expiration
openssl x509 -in /etc/letsencrypt/live/api.xoperr.dev/fullchain.pem -noout -dates

# Renew certificate
sudo certbot renew --force-renewal
```

---

## Environment Configuration

The service file includes:
- **OPENROUTER_API_KEY** - Replace with your actual key
- **PYTHONUNBUFFERED** - Ensures logging is unbuffered
- **MemoryMax=900M** - Hard limit of 900MB RAM

To update the API key after deployment:

```bash
sudo systemctl stop lessons-api

# Edit the service file
sudo nano /etc/systemd/system/lessons-api.service
# Update the OPENROUTER_API_KEY line

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl start lessons-api
```

---

## Performance Tuning

### Increase Nginx worker connections

Edit `/etc/nginx/nginx.conf`:
```nginx
events {
    worker_connections 2048;
}
```

Then:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Increase system file descriptors

Edit `/etc/security/limits.conf`:
```
* soft nofile 65536
* hard nofile 65536
```

Then reboot or:
```bash
ulimit -n 65536
```

### Adjust Uvicorn workers

Currently set to 2 workers. Options:
- **1 worker**: Minimum, saves RAM
- **2 workers**: Recommended for 1GB, good balance
- **4 workers**: Only on 2GB+ servers

Edit service file to change workers:
```bash
ExecStart=/usr/bin/uvicorn main:app --host 127.0.0.1 --port 5000 --workers 2
```

---

## Backup & Restore

### Backup data files

```bash
# Backup all data
tar -czf lessons-api-backup-$(date +%Y%m%d).tar.gz \
    /home/xoperr/projects/server/API/*.json

# Store safely
mv lessons-api-backup-*.tar.gz /path/to/backup/
```

### Restore from backup

```bash
tar -xzf lessons-api-backup-*.tar.gz -C /
sudo systemctl restart lessons-api
```

---

## Security Checklist

✅ SSL/TLS enabled (Let's Encrypt)
✅ Security headers configured (HSTS, X-Frame-Options, etc.)
✅ Nginx running as www-data
✅ FastAPI listening on localhost only (127.0.0.1:5000)
✅ File permissions proper
✅ Log files accessible
✅ Memory limited to 900M
✅ Automatic restart enabled

To add authentication to API (optional):

```bash
# Install apache2-utils
sudo apt install apache2-utils

# Create password file for /docs
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Add to nginx config:
location /docs {
    auth_basic "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://lessons_api;
}
```

---

## Health Check

Verify deployment is working:

```bash
# Check all components
echo "=== Service Status ===" && \
sudo systemctl status lessons-api | grep Active && \
echo "=== Nginx Status ===" && \
sudo systemctl status nginx | grep Active && \
echo "=== API Health ===" && \
curl -s https://api.xoperr.dev/health | python3 -m json.tool && \
echo "=== Memory ===" && \
free -h && \
echo "=== Uptime ===" && \
uptime
```

---

## Summary

Your Lessons API is now:
✅ Running on api.xoperr.dev
✅ Secured with HTTPS (Let's Encrypt)
✅ Behind Nginx reverse proxy
✅ Managed by systemd
✅ Optimized for 1GB RAM
✅ Auto-restarting on failure
✅ Monitored and logged

You can access:
- **API:** https://api.xoperr.dev/
- **Docs:** https://api.xoperr.dev/docs
- **Health:** https://api.xoperr.dev/health

