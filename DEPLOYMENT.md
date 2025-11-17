# SurfSense Production Deployment Guide

**Server**: ai.kapteinis.lv
**Date**: November 17, 2025
**Branch**: nightly
**Environment**: Debian VPS with local Ollama LLMs

---

## 📋 Pre-Deployment Checklist

✅ **Code Changes Committed:**
- Minimal privacy-focused frontend UI
- Email/password authentication only
- Google Analytics removed
- Anthropic Claude removed from examples
- Social media: Mastodon, Pixelfed, Bookwyrm only

✅ **GitHub Status:**
- All changes pushed to `nightly` branch
- Repository: https://github.com/okapteinis/SurfSense

✅ **Configuration Verified:**
- Mistral NeMo 128K context window fix applied
- TildeOpen 30B grammar checker configured
- Gemini API fallback configured
- No secrets committed to repository

---

## 🚀 Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
# On your VPS (ai.kapteinis.lv)
ssh your-user@ai.kapteinis.lv

# Create deployment script
cat > /opt/SurfSense/deploy.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 SurfSense Deployment to ai.kapteinis.lv"
echo "==========================================="

# Backup current state
BACKUP_DIR="/opt/SurfSense/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r /opt/SurfSense/surfsense_web "$BACKUP_DIR/"
echo "✅ Backup created: $BACKUP_DIR"

# Pull latest code
cd /opt/SurfSense
git fetch origin
git checkout nightly
git pull origin nightly
echo "✅ Code updated from GitHub"

# Install and build frontend
cd /opt/SurfSense/surfsense_web
pnpm install
pnpm build
echo "✅ Frontend built"

# Restart services
sudo systemctl restart surfsense
sudo systemctl restart surfsense-frontend
sudo systemctl restart surfsense-celery || true
sudo systemctl restart surfsense-celery-beat || true
echo "✅ Services restarted"

# Verify
sleep 5
echo ""
echo "Service Status:"
systemctl is-active surfsense && echo "  ✅ Backend: Running"
systemctl is-active surfsense-frontend && echo "  ✅ Frontend: Running"
systemctl is-active ollama && echo "  ✅ Ollama: Running"

echo ""
echo "🎉 Deployment complete!"
echo "🔗 Visit: https://ai.kapteinis.lv"
EOF

chmod +x /opt/SurfSense/deploy.sh

# Run deployment
/opt/SurfSense/deploy.sh
```

### Option 2: Manual Deployment

```bash
# 1. SSH to server
ssh your-user@ai.kapteinis.lv

# 2. Navigate to SurfSense directory
cd /opt/SurfSense

# 3. Backup current installation
mkdir -p backups/$(date +%Y%m%d_%H%M%S)
cp -r surfsense_web backups/$(date +%Y%m%d_%H%M%S)/

# 4. Pull latest changes
git fetch origin
git checkout nightly
git pull origin nightly

# 5. Install frontend dependencies
cd surfsense_web
pnpm install

# 6. Build frontend
pnpm build

# 7. Restart services
sudo systemctl restart surfsense
sudo systemctl restart surfsense-frontend
sudo systemctl restart surfsense-celery
sudo systemctl restart surfsense-celery-beat

# 8. Verify services are running
systemctl status surfsense
systemctl status surfsense-frontend
systemctl status ollama
```

---

## ✅ Post-Deployment Verification

### 1. Check Services Status

```bash
# All services should show "active (running)"
sudo systemctl status surfsense
sudo systemctl status surfsense-frontend
sudo systemctl status ollama
sudo systemctl status surfsense-celery
```

### 2. Verify UI Changes

Visit https://ai.kapteinis.lv and verify:

**Homepage Should Show:**
- ✅ SurfSense logo and theme toggle only (no navigation links)
- ✅ "Let's Start Surfing" heading
- ✅ Tagline paragraph
- ✅ Hero screenshot/demo
- ✅ Footer with SurfSense name and social links

**Homepage Should NOT Show:**
- ❌ "Get Started" button
- ❌ "Pricing" link
- ❌ "Docs" link
- ❌ Discord/GitHub icons
- ❌ "Sign In" button in navbar
- ❌ Feature cards or integrations sections

**Login Page Should Show:**
- ✅ Email and password fields only
- ✅ "Sign In" button
- ✅ Link to register page

**Login Page Should NOT Show:**
- ❌ "Continue with Google" button
- ❌ Any OAuth options

### 3. Test Authentication

```bash
# Test login endpoint
curl -X POST https://ai.kapteinis.lv/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'
```

### 4. Test LLM Backend

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# Should show mistral-nemo:128k and tildeopen models
```

### 5. Check Logs

```bash
# Backend logs
journalctl -u surfsense -n 100 -f

# Frontend logs
journalctl -u surfsense-frontend -n 100 -f

# Ollama logs
journalctl -u ollama -n 100 -f
```

Look for:
- ✅ No errors during startup
- ✅ "Context window=131072" in logs (Mistral NeMo)
- ✅ Successful model loading messages
- ✅ No Google Analytics references

---

## 🔧 Troubleshooting

### Frontend Build Fails

```bash
# Clear cache and rebuild
cd /opt/SurfSense/surfsense_web
rm -rf .next node_modules
pnpm install
pnpm build
```

### Services Won't Start

```bash
# Check for errors
journalctl -u surfsense -n 50
journalctl -u surfsense-frontend -n 50

# Verify ports are available
sudo lsof -i :8000  # Backend
sudo lsof -i :3000  # Frontend
sudo lsof -i :11434 # Ollama
```

### Ollama Models Missing

```bash
# List installed models
ollama list

# Re-pull if needed
ollama pull mistral-nemo
ollama create mistral-nemo:128k -f /path/to/mistral-nemo-128k.modelfile
ollama pull tildeopen:30b-q5_k_m
```

### Google Analytics Still Showing

```bash
# Verify layout.tsx doesn't have GA
grep -r "GoogleAnalytics\|google-analytics\|gtag" /opt/SurfSense/surfsense_web/app/

# Should return nothing
```

---

## 📊 Performance Monitoring

### After Deployment, Monitor:

```bash
# RAM usage (should be 20-25GB during inference)
free -h

# CPU usage
htop

# Disk space
df -h

# Response times
curl -w "@-" -o /dev/null -s https://ai.kapteinis.lv << 'EOF'
time_total: %{time_total}s
EOF
```

### Expected Performance:

- **English queries**: ~5 seconds
- **Latvian queries**: ~23 seconds (with grammar check)
- **RAM usage**: 13-15GB idle, 20-25GB during inference
- **Disk usage**: ~28GB for Ollama models

---

## 🔄 Rollback Procedure

If something goes wrong:

```bash
# Find backup
ls -lt /opt/SurfSense/backups/

# Restore from backup
cd /opt/SurfSense
mv surfsense_web surfsense_web.failed
cp -r backups/YYYYMMDD_HHMMSS/surfsense_web .

# Restart services
sudo systemctl restart surfsense-frontend
```

---

## 📝 Production Configuration

### Environment Variables

Location: `/opt/SurfSense/surfsense_backend/.env`

**Required:**
```bash
GEMINI_API_KEY=your_key_here
OLLAMA_BASE_URL=http://localhost:11434
SECRET_KEY=your_secret_key
DATABASE_URL=postgresql://...
REDIS_URL=redis://localhost:6379
```

**Not Required (Removed):**
```bash
# GOOGLE_OAUTH_CLIENT_ID  # OAuth disabled
# GOOGLE_OAUTH_CLIENT_SECRET  # OAuth disabled
# ANTHROPIC_API_KEY  # Not using Claude
```

### LLM Configuration

Location: `/opt/SurfSense/surfsense_backend/app/config/global_llm_config.yaml`

**Three-tier architecture:**
1. Mistral NeMo 12B (primary)
2. TildeOpen 30B (Latvian grammar)
3. Gemini 2.0 Flash (fallback)

See `global_llm_config.yaml.template` for structure.

---

## 🎯 Success Criteria

Deployment is successful when:

- ✅ Homepage shows minimal UI (logo + tagline only)
- ✅ No navigation links visible (Pricing, Docs removed)
- ✅ Login page shows email/password form only
- ✅ No Google OAuth button
- ✅ Footer shows only Mastodon, Pixelfed, Bookwyrm links
- ✅ Services all running (backend, frontend, Ollama)
- ✅ English queries respond in ~5 seconds
- ✅ Latvian queries respond in ~23 seconds
- ✅ No errors in logs
- ✅ RAM usage normal (13-25GB)

---

## 📞 Support

**Issues:** https://github.com/okapteinis/SurfSense/issues
**Email:** ojars@kapteinis.lv
**Deployment Date:** November 17, 2025
**Version:** nightly branch (commit 209cd24)

---

## 📚 Related Documentation

- `INSTALLATION_LOCAL_LLM.md` - Complete Ollama setup guide
- `MIGRATION_LOCAL_LLM.md` - Architecture and migration details
- `PR_DESCRIPTION.md` - Full PR documentation
- `claude.md` - Security audit report

---

**Deployment Complete!** Your minimal, privacy-focused SurfSense instance with local European AI is ready. 🎉
