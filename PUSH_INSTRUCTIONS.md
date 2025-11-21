# Instructions for Pushing Feature Branch to GitHub

## Branch Information
- **Branch Name:** `feature/fix-session-expiration-issue`
- **Base Branch:** `nightly`
- **Commits:** 5 commits ready to push

## Option 1: Push from VPS (Recommended)

### Step 1: Install GitHub CLI
```bash
# SSH into VPS
ssh -i ~/.ssh/id_ed25519_surfsense root@46.62.230.195

# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh -y
```

### Step 2: Authenticate with GitHub
```bash
gh auth login
# Follow the prompts:
# - Select: GitHub.com
# - Select: HTTPS
# - Authenticate: Yes
# - How: Login with a web browser (copy the one-time code)
```

### Step 3: Push the Branch
```bash
cd /opt/SurfSense
git push -u origin feature/fix-session-expiration-issue
```

### Step 4: Create Pull Request
```bash
gh pr create --base nightly --title "Fix session persistence and LLM configuration" --body-file FEATURE_BRANCH_SUMMARY.md
```

---

## Option 2: Push from Local Machine

### Step 1: Pull from VPS to Local
```bash
# On your local machine, in your SurfSense directory
git fetch --all
git checkout feature/fix-session-expiration-issue

# If branch doesn't exist locally, create it
git checkout -b feature/fix-session-expiration-issue origin/feature/fix-session-expiration-issue
```

### Step 2: Push to GitHub
```bash
git push -u origin feature/fix-session-expiration-issue
```

### Step 3: Create Pull Request
Go to: https://github.com/okapteinis/SurfSense/pulls

Or use GitHub CLI:
```bash
gh pr create --base nightly --title "Fix session persistence and LLM configuration" --body-file FEATURE_BRANCH_SUMMARY.md
```

---

## Pull Request Template

**Title:**
```
Fix session persistence and LLM configuration
```

**Description:**
```markdown
## Summary
This PR fixes two critical production issues:
1. Session persistence - resolves "Your session has expired" errors
2. LLM configuration - corrects model priority and secures API keys

## Changes
- Add nginx routing for /verify-token endpoint
- Reorder LLM models: Gemini (primary) → TildeOpen (grammar) → Mistral (fallback)
- Implement environment variable expansion for secure secret management
- Sanitize documentation to remove production details

## Testing
- ✅ Session persistence tested and working
- ✅ Backend starts without errors
- ✅ No secrets exposed in committed files
- ✅ All services running normally

## Documentation
- NGINX_SESSION_FIX.md
- LLM_CONFIG_FIX.md
- FEATURE_BRANCH_SUMMARY.md

## Deployment Notes
**Manual steps required:**
1. Update nginx configuration (see NGINX_SESSION_FIX.md)
2. Add GEMINI_API_KEY to .env file
3. Restart nginx and backend services

## Security Review
✅ All commits reviewed for sensitive information
✅ No API keys, domains, IPs, or passwords in code

See FEATURE_BRANCH_SUMMARY.md for complete details.
```

---

## Verification Checklist

Before merging:
- [ ] All commits pushed successfully
- [ ] Pull request created against `nightly` branch
- [ ] PR description includes all changes
- [ ] Documentation reviewed
- [ ] No secrets in committed files
- [ ] CI/CD checks passing (if configured)

---

## Need Help?

If you encounter authentication issues:
1. Check GitHub permissions for the repository
2. Verify SSH key or HTTPS token is configured
3. Join SurfSense Discord for community support
