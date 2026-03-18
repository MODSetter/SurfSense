# Desktop App — Required Before Distribution

## Status: Internal testing ✅ | Production distribution ❌

---

## P0 — Blockers (app won't work for end users without these)

### 1. Backend connectivity for hosted users
**Problem:** Desktop app hardcodes `NEXT_PUBLIC_FASTAPI_BACKEND_URL=http://localhost:8000`.
Hosted/cloud users don't run a local backend — they need it pointed at the production API.

**Files:** `surfsense_desktop/src/resolve-env.ts` (defaults), `.env` in standalone output

**Work:**
- [ ] Build Next.js with placeholder values (`__NEXT_PUBLIC_FASTAPI_BACKEND_URL__`)
- [ ] Hosted build: resolve-env replaces with production backend URL
- [ ] Self-hosted: resolve-env keeps localhost defaults (or reads user config)
- [ ] Same for `NEXT_PUBLIC_ELECTRIC_URL`, `NEXT_PUBLIC_ELECTRIC_AUTH_MODE`, `NEXT_PUBLIC_DEPLOYMENT_MODE`

### 2. `HOSTED_FRONTEND_URL` must be dynamic
**Problem:** `main.ts` hardcodes `https://surfsense.net`. OAuth redirect interception breaks if production domain changes (.com, custom domain, self-hosted).

**File:** `surfsense_desktop/src/main.ts:16`

**Work:**
- [ ] Load from `.env` file (dotenv) or fetch from backend endpoint
- [ ] Self-hosted users must be able to configure this

### 3. `resolve-env.ts` is destructive
**Problem:** Placeholder replacement modifies JS files in-place. After first launch, placeholders are gone. Self-hosted users can't change their backend URL without reinstalling.

**File:** `surfsense_desktop/src/resolve-env.ts:1`

**Work:**
- [ ] Keep a pristine copy of the standalone output
- [ ] Replace placeholders into a working copy on each launch
- [ ] Or: use a different mechanism (env vars at server startup, not file patching)

### 4. Port conflict handling
**Problem:** Port 3000 is hardcoded. If occupied, app fails silently with no window.

**File:** `surfsense_desktop/src/main.ts:8`

**Work:**
- [ ] Use `get-port-please` to find a free port (reference project uses this)
- [ ] Pass dynamic port to all URL references

---

## P1 — Required for public release

### 5. macOS code signing & notarization
**Problem:** Ad-hoc signed. Gatekeeper warns users, some will refuse to install.

**Work:**
- [ ] Apple Developer account ($99/year)
- [ ] Configure signing identity in `electron-builder.yml`
- [ ] Enable notarization (required since macOS 10.15)

### 6. App icon
**Problem:** Default Electron icon. Looks unprofessional.

**Work:**
- [ ] Design/export SurfSense icon as `.icns` (macOS), `.ico` (Windows), `.png` (Linux)
- [ ] Place in `surfsense_desktop/assets/`
- [ ] Paths already configured in `electron-builder.yml`

### 7. Native menu bar
**Problem:** Without a custom menu, Cmd+C / Cmd+V / Cmd+A don't work on macOS.

**Work:**
- [ ] Create `Menu.buildFromTemplate()` with standard Edit menu items
- [ ] Add App menu (About, Quit), View (Reload, DevTools), Window, Help

### 8. Error handling & user feedback
**Problem:** If the Next.js server fails to start, user sees nothing — blank screen or no window.

**Work:**
- [ ] Show error dialog if server fails (`dialog.showErrorBox`)
- [ ] Loading splash screen while server starts
- [ ] Handle `unhandledRejection` and `uncaughtException`

### 9. Windows & Linux builds
**Problem:** Only macOS tested. Windows (NSIS) and Linux (deb/AppImage) untested.

**Work:**
- [ ] Test `pnpm dist:win` and `pnpm dist:linux` (ideally in CI)
- [ ] Windows: optional code signing (EV cert for SmartScreen)
- [ ] Linux: verify deep link registration via `.desktop` file

---

## P2 — Should have for v1.0

### 10. Auto-updater
`electron-updater` is installed but not wired. Users currently have no way to update.
- [ ] Configure with GitHub Releases
- [ ] Background download, install on restart

### 11. Reduce bundle size
Desktop ships marketing pages (landing, /pricing, /docs, /contact) unnecessarily.
- [ ] Separate app routes from marketing routes in `next.config.ts`
- [ ] Or: exclude marketing routes from standalone trace

### 12. CI/CD pipeline
- [ ] GitHub Actions workflow: build for macOS/Windows/Linux on tag push
- [ ] Upload artifacts to GitHub Releases
- [ ] Auto-updater reads from these releases

---

## Done ✅

- [x] Electron project scaffolding
- [x] Next.js standalone integration (in-process `require()`)
- [x] pnpm symlink resolution + flattening for electron-builder
- [x] OAuth redirect interception (`webRequest.onBeforeRequest`)
- [x] Backend CORS for localhost
- [x] Deep link protocol registration (`surfsense://`)
- [x] Single instance lock
- [x] Secure BrowserWindow defaults (contextIsolation, sandbox, no nodeIntegration)
- [x] External links open in system browser
- [x] macOS .dmg builds (arm64 + x64)
- [x] Login/auth flow tested and working
