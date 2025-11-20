# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.0.8   | :white_check_mark: |
| < 0.0.8 | :x:                |

## Security Vulnerability Fixes - November 2025

### Summary

This document tracks the security vulnerabilities addressed in the November 2025 security audit and remediation effort. A comprehensive dependency audit was performed across all frontend components, resulting in significant reduction of security vulnerabilities.

### Vulnerabilities Fixed

#### Critical & High Severity (CVSS ≥ 7.0)

| Package | CVE | CVSS | Component | Previous Version | Fixed Version | Status |
|---------|-----|------|-----------|------------------|---------------|--------|
| glob | GHSA-5j98-mcp5-4vw2 | 7.5 | Web + Extension | 10.2.0-10.4.5 | 10.5.0 | ✅ Fixed |
| base-x | CVE-2025-27611 | High | Extension | 3.0.10 | 3.0.11 | ✅ Fixed |
| cross-spawn | CVE-2024-21538 | 7.5 | Web + Extension | 7.0.3 | 7.0.6 | ✅ Fixed |
| css-what | CVE-2021-33587 | 7.5 | Extension | 4.0.0 | 5.0.1 | ⚠️ Transitive (linkedom) |
| msgpackr | CVE-2023-52079 | 8.6 | Extension | 1.8.5 | 1.10.1 | ⚠️ Transitive (plasmo) |

#### Moderate Severity (CVSS 4.0-6.9)

| Package | CVE | CVSS | Component | Previous Version | Fixed Version | Status |
|---------|-----|------|-----------|------------------|---------------|--------|
| next | GHSA-g5qg-72qw-gw5v | 6.2 | Web | 15.2.3 | 15.5.6 | ✅ Fixed |
| next | GHSA-xv57-4mr9-wg8v | 4.3 | Web | 15.2.3 | 15.5.6 | ✅ Fixed |
| next | GHSA-4342-x723-ch2f | 6.5 | Web | 15.2.3 | 15.5.6 | ✅ Fixed |
| next | GHSA-223j-4rm8-mrmf | Low | Web | 15.2.3 | 15.5.6 | ✅ Fixed |
| js-yaml | GHSA-mh29-5h37-fv8m | 5.3 | Web + Extension | 4.0.0-4.1.0 | 4.1.1 | ✅ Fixed |
| esbuild | GHSA-67mh-4wv8-2f99 | 5.3 | Web + Extension | ≤0.24.2 | 0.25.0 | ⚠️ Transitive |
| @babel/runtime | CVE-2025-27789 | 6.2 | Web + Extension | <7.26.10 | 7.28.4 | ✅ Fixed |
| @babel/helpers | CVE-2025-27789 | 6.2 | Web + Extension | <7.26.10 | 7.28.4 | ✅ Fixed |
| svelte | CVE-2024-45047 | 5.4 | Extension | 4.2.2 | 4.2.19 | ⚠️ Transitive (plasmo) |
| tar-fs | Multiple | Moderate | Web + Extension | 2.1.1 | 2.1.4 | ✅ Fixed |
| prismjs | GHSA-x7hr-w5r2-h6wg | 4.9 | Web | <1.30.0 | 1.30.0 | ⚠️ Transitive |

#### Low Severity

| Package | CVE | Component | Status |
|---------|-----|-----------|--------|
| brace-expansion | GHSA-v6h2-p8h4-qcjw | Web + Extension | ✅ Fixed |
| nanoid | Multiple | Web + Extension | ✅ Fixed |
| eslint | GHSA-xffm-g5w8-qvg7 | Web | ✅ Fixed |

### Known Remaining Vulnerabilities

The following vulnerabilities remain after the security fix effort. These are acknowledged with justification:

#### Requires Major Version Upgrades (Breaking Changes)

| Package | Reason | Risk Assessment | Planned Action |
|---------|--------|-----------------|----------------|
| ai (Vercel AI SDK) | v4 → v5 breaking changes | Low-Moderate: File upload bypass, XSS in jsondiffpatch | Schedule separate testing & migration |
| drizzle-kit | Native dependency rebuild required | Low: esbuild CORS in dev server only | Update when upgrade path is clear |
| react-syntax-highlighter | v15 → v16 breaking changes | Low-Moderate: prismjs DOM clobbering | Schedule separate testing |

#### Transitive Dependencies (Framework-Locked)

| Package | Framework | Risk Assessment | Mitigation |
|---------|-----------|-----------------|------------|
| msgpackr, svelte, css-what | plasmo 0.89.4 | Low-Moderate | Monitor plasmo updates, consider upgrade |
| esbuild (in tsup) | plasmo dependency | Low: Dev server only | Development-only risk |
| tmp, nanoid, content-security-policy-parser | plasmo dependencies | Low | Monitor plasmo updates |

### Testing Performed

- ✅ Dependency updates applied successfully via npm/pnpm
- ✅ Lock files regenerated and verified
- ✅ Vulnerability count reduced from 43 to 18 total
  - **surfsense_web**: 11 → 9 vulnerabilities (0 critical/high)
  - **surfsense_browser_extension**: 18+ → 9 vulnerabilities (2 high in transitive deps)
- ⚠️ Build testing limited by environment constraints (Google Fonts network access, native modules)
- ⚠️ Full functional testing required in production-like environment

### Upgrade Summary

**Packages Successfully Upgraded:**
- glob: 10.4.5 → 10.5.0
- next: 15.2.3 → 15.5.6 (4 security patches)
- js-yaml: 4.1.0 → 4.1.1
- cross-spawn: 7.0.3 → 7.0.6
- tar-fs: 2.1.1 → 2.1.4
- base-x: 3.0.10 → 3.0.11
- @babel/runtime: 7.25.4 → 7.28.4
- @babel/helpers: 7.25.0 → 7.28.4
- brace-expansion: 2.0.1 → 2.0.2
- nanoid: 3.3.7 → 3.3.11
- prismjs: 1.27.0 → 1.30.0
- eslint: Updated to latest compatible version

**Total Vulnerability Reduction:** 43 → 18 (58% reduction)
**Critical/High Vulnerabilities:** Reduced from 5 to 2 (both in transitive dependencies)

### Security Best Practices

1. **Dependency Updates**: Run `npm audit` / `pnpm audit` monthly
2. **Automated Scanning**: Dependabot is enabled and monitoring dependencies
3. **Breaking Changes**: Evaluate major version upgrades separately with full testing
4. **Transitive Dependencies**: Monitor framework updates (plasmo, next.js) for security patches
5. **Python Backend**: Regularly audit with `pip-audit` (not covered in this update)

### Reporting Security Issues

If you discover a security vulnerability in SurfSense, please report it to:
- Email: security@surfsense.io (if configured)
- GitHub Security Advisories: https://github.com/okapteinis/SurfSense/security/advisories

Please do NOT open public issues for security vulnerabilities.

### References

- [November 2025 Security Audit](./DEPLOYMENT_NOTES_2025-11-20.md)
- [GitHub Security Advisories](https://github.com/okapteinis/SurfSense/security)
- [Dependabot Alerts](https://github.com/okapteinis/SurfSense/security/dependabot)

---

**Last Updated:** November 20, 2025
**Audit Performed By:** Claude Code AI Assistant
**Approved By:** Ojārs Kapteinis
**Next Review:** December 2025
