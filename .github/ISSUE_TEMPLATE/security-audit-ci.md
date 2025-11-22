---
name: Security Audit CI/CD
about: Automate security dependency audits in continuous integration
title: 'Automate Security Audits for Dependencies'
labels: 'security, maintenance, ci/cd'
assignees: ''
---

## Summary
Integrate automated security dependency audits into the CI/CD pipeline to catch vulnerabilities early and ensure dependencies remain secure throughout the development lifecycle.

## Motivation
Although dependencies are currently up-to-date, automated audits ensure that any future vulnerabilities are caught early before merging to production branches. This is critical for:
- **Continuous Security**: Proactive vulnerability detection
- **Compliance**: Meeting security audit requirements
- **Risk Mitigation**: Preventing vulnerable dependencies from reaching production
- **Team Awareness**: Developers are immediately notified of security issues

## Proposed Implementation

### Frontend Security Audits (npm)
```yaml
# .github/workflows/security-audit-frontend.yml
name: Frontend Security Audit
on:
  push:
    branches: [main, nightly]
  pull_request:
    branches: [main, nightly]
  schedule:
    - cron: '0 2 * * 1' # Weekly on Mondays at 2 AM

jobs:
  npm-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Run npm audit
        working-directory: ./surfsense_web
        run: |
          # Save audit results to JSON for artifact upload
          npm audit --audit-level=high --json > npm-audit.json || true
          # Fail pipeline if high-severity vulnerabilities found
          npm audit --audit-level=high
      - name: Upload audit results
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: npm-audit-results
          path: surfsense_web/npm-audit.json
```

### Backend Security Audits (pip)
```yaml
# .github/workflows/security-audit-backend.yml
name: Backend Security Audit
on:
  push:
    branches: [main, nightly]
  pull_request:
    branches: [main, nightly]
  schedule:
    - cron: '0 2 * * 1' # Weekly on Mondays at 2 AM

jobs:
  pip-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install pip-audit
        run: pip install pip-audit
      - name: Run pip audit
        working-directory: ./surfsense_backend
        run: |
          # Save audit results to JSON for artifact upload
          pip-audit --requirement requirements.txt --format json > audit.json || true
          # Fail pipeline if high/critical vulnerabilities found
          pip-audit --requirement requirements.txt --desc --vulnerability-service osv
      - name: Upload audit results
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: pip-audit-results
          path: surfsense_backend/audit.json
```

## Acceptance Criteria
- [x] Workflows created in `.github/workflows/`
  - `security-audit-frontend.yml`
  - `security-audit-backend.yml`
- [ ] Tests triggered on:
  - Push to `main` and `nightly` branches
  - Pull requests targeting `main` and `nightly`
  - Weekly schedule (Monday 2 AM)
- [ ] Pipeline fails on:
  - High-severity vulnerabilities (frontend)
  - High/Critical vulnerabilities (backend)
- [ ] Audit results uploaded as artifacts on failure
- [ ] Branch protection rules updated to require audit checks
- [ ] Team notification configured (Slack/email) on audit failures

## Testing Plan
1. Create workflow files in `.github/workflows/`
2. Test with intentionally vulnerable dependency
3. Verify pipeline fails appropriately
4. Verify audit artifacts are uploaded
5. Test scheduled execution (wait for Monday or trigger manually)
6. Update branch protection rules
7. Document findings and tune thresholds if needed

## Documentation Updates
- [ ] Update `README.md` with CI/CD badge for security audits
- [ ] Add section to `SECURITY.md` describing automated audit process
- [ ] Document how to review and address audit findings
- [ ] Add troubleshooting guide for common audit issues

## Architecture Impact
- **Low Impact**: Purely additive CI/CD workflows
- **No Runtime Changes**: Does not affect production code
- **Branch Protection**: May require updating branch protection rules

## Related Issues/PRs
- Addresses continuous improvement recommendation #1
- Related to security hardening efforts

## Priority
**High** - Security vulnerabilities can be introduced at any time through dependency updates.

## Effort Estimate
- **Workflow Creation**: 2-3 hours
- **Testing & Tuning**: 2-4 hours
- **Documentation**: 1-2 hours
- **Total**: 1-2 days

## References
- [npm audit documentation](https://docs.npmjs.com/cli/v8/commands/npm-audit)
- [pip-audit GitHub](https://github.com/pypa/pip-audit)
- [GitHub Actions security best practices](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- Current dependencies are at version 0.0.8-LV01 (all up-to-date)
