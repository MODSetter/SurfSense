# SurfSense Desktop App — Complete Implementation Plan

## Decision: Electron + Next.js Standalone

### Why Electron
- Electron bundles Node.js + Chromium → runs the full Next.js standalone server as-is
- Zero frontend code changes required (no `output: "export"`, no routing rewrite)
- SurfSense uses dynamic routes, API routes, server components, `next-intl`, middleware — all incompatible with static export
- Tauri and Nextron both require `output: "export"` which breaks all of the above
- Evidence: `next-electron-rsc` library (131 stars), Feb 2026 Medium article with production template
- Reference project: CodePilot (4,155 stars) — Electron + Next.js desktop app using electron-builder + esbuild

### Architecture
```
surfsense_desktop/
├── src/
│   ├── main.ts          ← Electron main process (Node.js)
│   │   ├── Spawns Next.js standalone server as child process
│   │   ├── Registers deep link protocol (surfsense://)
│   │   ├── Creates BrowserWindow pointing to Next.js
│   │   ├── System tray, global shortcuts, native menus
│   │   └── IPC handlers (safeStorage, clipboard, notifications)
│   └── preload.ts       ← contextBridge for secure renderer↔main IPC
├── scripts/
│   └── build-electron.mjs  ← esbuild script to compile TS
├── assets/              ← App icons (icns, ico, png, tray)
├── electron-builder.yml ← Packaging config for macOS/Windows/Linux
└── package.json
```

### What Stays Unchanged
- `surfsense_web/` — entire frontend codebase (zero changes)
- `surfsense_backend/` — almost unchanged (1 CORS line for hosted users)
- `next.config.ts` — keeps `output: "standalone"`
- All 13 connector OAuth flows — happen in system browser, Electric SQL syncs results

---

## Phase 1: Electron Shell Setup

### 1.1 — Project structure and dependencies

- [x] Create `surfsense_desktop/` directory at repo root
- [x] Initialize with `pnpm init`
- [x] Install dependencies:
  - `electron` (dev) — desktop shell
  - `electron-builder` (dev) — packaging/distribution
  - `esbuild` (dev) — compile Electron TypeScript files
  - `concurrently` (dev) — run Next.js dev + Electron together
  - `wait-on` (dev) — wait for Next.js dev server before launching Electron
  - `electron-updater` (prod) — auto-update
  - `typescript` (dev), `@types/node` (dev) — TypeScript support
- [ ] Create `tsconfig.json` for Electron TypeScript files
- [ ] Create folder structure (`src/`, `scripts/`, `assets/`)
- [ ] Add npm scripts:
  - `dev` — `concurrently -k "next dev" "wait-on http://localhost:3000 && electron ."`
  - `electron:build` — `next build && node scripts/build-electron.mjs`
  - `electron:pack` — `electron:build && electron-builder --config electron-builder.yml`

### 1.2 — Main process (`main.ts`)

- [ ] Create `BrowserWindow` with secure defaults:
  - `contextIsolation: true`
  - `nodeIntegration: false`
  - `sandbox: true`
  - `webviewTag: false`
- [ ] Load content based on mode:
  - Dev mode: `win.loadURL('http://localhost:3000')`
  - Production: Spawn `node server.js` from `.next/standalone/`, wait for ready, load `http://localhost:{port}`
- [ ] Handle `window-all-closed` (quit on Windows/Linux, stay alive on macOS)
- [ ] Handle `activate` (re-create window on macOS dock click)
- [ ] Set app user model ID on Windows: `app.setAppUserModelId('com.surfsense.desktop')`
- [ ] Handle `will-quit` to clean up child processes

### 1.3 — Preload script (`preload.ts`)

- [ ] Use `contextBridge.exposeInMainWorld` to expose safe IPC channels:
  - Auth: `storeToken`, `getToken`, `clearToken`
  - Native: `openExternal`, `getClipboardText`, `showNotification`
  - App info: `getAppVersion`, `getPlatform`
  - Deep link: `onDeepLink` callback
- [ ] Do NOT expose `ipcRenderer` directly

### 1.4 — Handle ASAR packaging and path resolution

- [ ] Use `app.getAppPath()` instead of `__dirname` for locating bundled assets
- [ ] Configure `electron-builder.yml` with `asarUnpack: [".next/standalone/**"]`
- [ ] Verify `public/` and `.next/static/` are accessible after packaging
- [ ] Test with `electron-builder --dir` before full packaging

### 1.5 — Native menu bar (`menu.ts`)

- [ ] Create application menu (required for Cmd+C/Cmd+V to work on macOS)
- [ ] Standard items: App (About, Preferences, Quit), Edit (Undo, Redo, Cut, Copy, Paste, Select All), View (Reload, DevTools, Zoom), Window, Help
- [ ] Keyboard accelerators: `CmdOrCtrl+,` → Settings, `CmdOrCtrl+N` → New chat, `CmdOrCtrl+Q` → Quit

---

## Phase 2: Environment Variables & Runtime Configuration

### 2.1 — Handle `NEXT_PUBLIC_*` variables at build time

| Variable | Electron Build Value | Notes |
|----------|---------------------|-------|
| `NEXT_PUBLIC_FASTAPI_BACKEND_URL` | See 2.2 | Must point to actual backend |
| `NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE` | `GOOGLE` or `LOCAL` | Match target deployment |
| `NEXT_PUBLIC_ETL_SERVICE` | `DOCLING` | Current default |
| `NEXT_PUBLIC_ELECTRIC_URL` | See 2.2 | Must point to Electric service |
| `NEXT_PUBLIC_ELECTRIC_AUTH_MODE` | `insecure` or `secure` | Match target deployment |
| `NEXT_PUBLIC_DEPLOYMENT_MODE` | `self-hosted` or `cloud` | Controls feature visibility |
| `NEXT_PUBLIC_POSTHOG_KEY` | Empty string OR real key | See 2.4 |
| `NEXT_PUBLIC_POSTHOG_HOST` | Empty string OR real host | See 2.4 |
| `NEXT_PUBLIC_APP_VERSION` | From `package.json` | Can auto-detect |

- [ ] Create `.env.electron` file with Electron-specific values
- [ ] Add build script that copies `.env.electron` before `next build`

### 2.2 — Runtime backend URL configuration (self-hosted users)

- [ ] Adapt `surfsense_web/docker-entrypoint.js` placeholder replacement for Electron:
  - Build Next.js with placeholder values (e.g. `__NEXT_PUBLIC_FASTAPI_BACKEND_URL__`)
  - On Electron startup, before spawning the Next.js server, run the same string replacement on `.next/standalone/` files
  - Read target values from `electron-store` (self-hosted) or use hosted defaults (cloud)
- [ ] Add "Self-Hosted?" link at the bottom of the login page:
  - Clicking reveals Backend URL and Electric URL input fields
  - User fills in their URLs, clicks Save → stored in `electron-store`
  - Electron re-runs placeholder replacement with new values, restarts the Next.js server
  - This link is only visible in the Electron app (detect via `window.electronAPI`)
  - Hosted users never see or interact with this
- [ ] `INTERNAL_FASTAPI_BACKEND_URL` (used in `verify-token/route.ts`, defaults to `http://backend:8000`): Set via `process.env` before spawning the Next.js server. For hosted builds, use the production backend URL. For self-hosted, use the same URL the user configured.

### 2.3 — Handle the contact form API route

- [ ] `surfsense_web/app/api/contact/route.ts` uses Drizzle ORM with `DATABASE_URL` to insert directly into PostgreSQL
- [ ] Desktop app does NOT have a direct PostgreSQL connection
- [ ] The contact form is a landing page feature. Desktop app starts at `/login` → never hits this route. Verify this is the case.
- [ ] If reachable: make it return 503 when `DATABASE_URL` is unset

### 2.4 — PostHog analytics in desktop

- [ ] PostHog is initialized only when `NEXT_PUBLIC_POSTHOG_KEY` is set
- [ ] Decision: Build with `NEXT_PUBLIC_POSTHOG_KEY=""` to disable in v1. Re-enable in v2 with `platform: 'desktop'` property.

---

## Phase 3: Authentication

### 3.1 — Email/password login (should work as-is)

- [ ] Verify login page renders in Electron
- [ ] Verify POST to `{BACKEND_URL}/auth/jwt/login` succeeds
- [ ] Verify token stored in localStorage (`surfsense_bearer_token`, `surfsense_refresh_token`)
- [ ] Verify `authenticatedFetch` includes Bearer token
- [ ] Verify token refresh on 401
- [ ] Verify logout clears tokens and redirects to `/login`

### 3.2 — Google OAuth login via deep link

- [ ] Register `surfsense://` protocol via `app.setAsDefaultProtocolClient("surfsense")`
- [ ] Intercept "Login with Google" → open in system browser via `shell.openExternal()`
- [ ] Append `?source=desktop&redirect_uri=surfsense://auth/callback` to authorize URL
- [ ] **Backend change** (`users.py`, ~5 lines): If `redirect_uri` starts with `surfsense://`, redirect there instead of `{NEXT_FRONTEND_URL}/auth/callback`
- [ ] Handle deep link in Electron:
  - macOS: `app.on('open-url')`
  - Windows/Linux: `app.on('second-instance')`
  - Parse URL, extract tokens, inject into renderer, navigate to `/dashboard`
- [ ] Platform notes:
  - macOS: requires packaged `.app` (not `electron .` dev mode)
  - Windows: works in dev mode
  - Linux `.deb`: registers `.desktop` file with `MimeType=x-scheme-handler/surfsense;`
  - Linux AppImage: known issues on some DEs

### 3.3 — Secure token storage

- [ ] v1: Use localStorage (matches web behavior)
- [ ] v2: Upgrade to `electron.safeStorage` for encrypted storage

### 3.4 — Handle `?source=desktop` on the web

- [ ] `TokenHandler.tsx` checks for `source=desktop` param
- [ ] If present: redirect to `surfsense://auth/callback?token=...&refresh_token=...`
- [ ] If absent: normal web behavior

---

## Phase 4: CORS and Backend Connectivity

### 4.1 — CORS for hosted/SaaS users

- [ ] Add localhost origins unconditionally in `surfsense_backend/app/app.py` (1-line change):
  ```python
  allowed_origins.extend(["http://localhost:3000", "http://127.0.0.1:3000"])
  ```
- [ ] Self-hosted: already works (localhost in `NEXT_FRONTEND_URL`)

### 4.2 — `INTERNAL_FASTAPI_BACKEND_URL` for `verify-token/route.ts`

- [ ] Set `INTERNAL_FASTAPI_BACKEND_URL` via `process.env` before spawning Next.js server
- [ ] Hosted: hardcode production backend URL
- [ ] Self-hosted: use user-configured URL

### 4.3 — Verify Fumadocs search route

- [ ] `app/api/search/route.ts` uses static MDX content — should work as-is
- [ ] Verify search works in Electron

---

## Phase 5: Connector OAuth Flows (13 connectors)

### 5.1 — Desktop connector OAuth (via system browser)

- [ ] Intercept connector OAuth URLs → open in system browser via `shell.openExternal()`
- [ ] Detection via `webContents.setWindowOpenHandler` and `webContents.on('will-navigate')`
- [ ] Electric SQL syncs new connectors to Electron automatically
- [ ] **Zero backend changes needed**

### 5.2 — Complete connector list

| # | Connector | Auth Endpoint |
|---|-----------|--------------|
| 1 | Airtable | `/api/v1/auth/airtable/connector/add/` |
| 2 | Notion | `/api/v1/auth/notion/connector/add/` |
| 3 | Google Calendar | `/api/v1/auth/google/calendar/connector/add/` |
| 4 | Google Drive | `/api/v1/auth/google/drive/connector/add/` |
| 5 | Gmail | `/api/v1/auth/google/gmail/connector/add/` |
| 6 | Slack | `/api/v1/auth/slack/connector/add/` |
| 7 | Microsoft Teams | `/api/v1/auth/teams/connector/add/` |
| 8 | Discord | `/api/v1/auth/discord/connector/add/` |
| 9 | Jira | `/api/v1/auth/jira/connector/add/` |
| 10 | Confluence | `/api/v1/auth/confluence/connector/add/` |
| 11 | Linear | `/api/v1/auth/linear/connector/add/` |
| 12 | ClickUp | `/api/v1/auth/clickup/connector/add/` |
| 13 | Composio | `/api/v1/auth/composio/connector/add/?toolkit_id=...` |

### 5.3 — Non-OAuth connectors

- [ ] Luma (API key) — works as-is
- [ ] File upload — works as-is
- [ ] YouTube crawler — works as-is

---

## Phase 6: Security Hardening

### 6.1 — BrowserWindow security

- [ ] `contextIsolation: true` (MANDATORY)
- [ ] `nodeIntegration: false` (MANDATORY)
- [ ] `sandbox: true`
- [ ] `webviewTag: false`
- [ ] Do NOT use `webSecurity: false` or `allowRunningInsecureContent: true`

### 6.2 — Content Security Policy

- [ ] Set CSP via `session.defaultSession.webRequest.onHeadersReceived`
- [ ] Block navigation to untrusted origins

### 6.3 — External link handling

- [ ] All external links open in system browser, not Electron window
- [ ] Implement in `webContents.setWindowOpenHandler` and `will-navigate`

### 6.4 — Process management

- [ ] Kill Next.js server on app quit (`will-quit`)
- [ ] Kill on crash (`render-process-gone`)
- [ ] Handle port conflicts

---

## Phase 7: Native Desktop Features

### 7.1 — System tray
- [ ] Tray icon with context menu (Open, New Chat, Quit)
- [ ] Minimize to tray on window close

### 7.2 — Global keyboard shortcut
- [ ] `CmdOrCtrl+Shift+S` to show/focus app
- [ ] Unregister on `will-quit`

### 7.3 — Native notifications
- [ ] Sync completed, new mentions, report generation
- [ ] Wire to Electric SQL shape updates

### 7.4 — Clipboard integration
- [ ] `clipboard.readText()` / `clipboard.writeText()` via IPC

### 7.5 — File drag-and-drop
- [ ] Verify `react-dropzone` works in Electron (should work as-is)

### 7.6 — Window state persistence
- [ ] Save/restore window position, size, maximized state

---

## Phase 8: Internationalization

- [ ] Verify `next-intl` works in Electron (5 locales: en, es, pt, hi, zh)
- [ ] Verify locale switching and persistence
- [ ] Verify URL-based locale prefix works

---

## Phase 9: Packaging and Distribution

### 9.1 — `electron-builder.yml` configuration
- [ ] Configure for macOS (.dmg), Windows (.exe NSIS), Linux (.deb + AppImage)
- [ ] Include `.next/standalone`, `.next/static`, `public` as extra resources
- [ ] `asarUnpack` for standalone server
- [ ] Exclude `node_modules/typescript`, `.next/cache`, source maps

### 9.2 — macOS build
- [ ] Code signing (Apple Developer certificate, $99/year)
- [ ] Notarization (required since macOS 10.15)
- [ ] Universal binary (Intel + Apple Silicon)

### 9.3 — Windows build
- [ ] NSIS installer
- [ ] Optional code signing (EV cert for SmartScreen)

### 9.4 — Linux build
- [ ] `.deb` (primary), AppImage (secondary)
- [ ] Deep link registration via `.desktop` file

### 9.5 — Auto-updater
- [ ] `electron-updater` with GitHub Releases
- [ ] Background download, install on restart

### 9.6 — App icons
- [ ] `.icns` (macOS), `.ico` (Windows), `.png` (Linux), tray icons

---

## Phase 10: CI/CD Pipeline

### 10.1 — GitHub Actions workflow
- [ ] `.github/workflows/desktop-build.yml`
- [ ] Matrix: macOS (.dmg), Windows (.exe), Ubuntu (.deb + AppImage)
- [ ] Steps: checkout → setup Node → build Next.js → build Electron → package → upload to GitHub Releases

### 10.2 — Release process
- [ ] Tag-based: `git tag v0.1.0 && git push --tags`
- [ ] `electron-updater` checks GitHub Releases for update manifests

---

## Phase 11: Development Workflow

- [ ] Dev: Terminal 1 `next dev`, Terminal 2 `electron .` (or single `pnpm dev` with concurrently)
- [ ] DevTools enabled in dev mode
- [ ] `pnpm run pack` for quick local testing without installer

---

## Phase 12: Testing

### 12.1 — Functional (all platforms)
- [ ] Login, dashboard, chat, document upload/editor, search, settings, team management, i18n, dark mode

### 12.2 — Electric SQL real-time
- [ ] Notifications, connectors, documents, messages, comments sync in real-time
- [ ] Data persists across restart (PGlite IndexedDB)

### 12.3 — Auth flows
- [ ] Email/password, Google OAuth via deep link (macOS/Windows/Linux), token refresh, logout

### 12.4 — Connector OAuth (at least 3)
- [ ] Slack, Notion, Google Drive via system browser → Electric SQL sync

### 12.5 — Native features
- [ ] System tray, global shortcut, notifications, menu bar (Cut/Copy/Paste)

### 12.6 — Platform-specific
- [ ] macOS (latest, Apple Silicon), Windows 10/11, Ubuntu 22.04/24.04 (.deb), Fedora (AppImage)

### 12.7 — Edge cases
- [ ] Single instance lock, network disconnection, backend unreachable, high DPI, multi-monitor

---

## Phase 13: Documentation

- [ ] User-facing: download links, self-hosted config guide, known limitations
- [ ] Developer-facing: README in `surfsense_desktop/`, architecture diagram, dev workflow, debug guide

---

## Summary of Backend Changes Required

| Change | File | Scope |
|--------|------|-------|
| CORS: always allow localhost | `app/app.py` | 1 line |
| Google OAuth: accept `surfsense://` redirect | `app/users.py` | ~5 lines |
| Pass `redirect_uri` through OAuth flow | `app/users.py` + `app/app.py` | ~10 lines |

**Total: ~16 lines of backend changes. Zero connector changes. Zero frontend changes (except optional `electronAPI` detection).**

---

## Decisions (Resolved)

### 1. `next-electron-rsc` vs child process?
**Decision: Child process (spawn `node server.js`).**
Standard pattern, no third-party dependency risk. Used by CodePilot (4,155 stars).

### 2. Runtime config for self-hosted users?
**Decision: Single build. Adapt `docker-entrypoint.js` placeholder pattern for Electron.**
- Hosted users: placeholders replaced with hosted defaults automatically. App goes straight to `/login`. No config UI.
- Self-hosted users: "Self-Hosted?" link at bottom of login page reveals Backend URL and Electric URL fields. Stored in `electron-store`, persists across restarts.
- Single build = 3 installers (not 6), one CI pipeline.

### 3. Which Electron version to target?
**Decision: Latest stable at time of implementation.**
Verify Node.js >= 18.18 (Next.js 16 requirement) and Chromium WASM support for PGlite.

### 4. Secure token storage in v1?
**Decision: localStorage in v1.**
Matches web behavior. Upgrade to `safeStorage` in v2.

### 5. Landing page in desktop app?
**Decision: Skip it. Start at `/login` (or `/dashboard` if authenticated).**
Landing page contact form needs `DATABASE_URL` — irrelevant for desktop users.

### 6. Separate builds for hosted vs self-hosted?
**Decision: Single build.**
Uses `docker-entrypoint.js` placeholder pattern for runtime URL configuration. Hosted defaults applied automatically. Self-hosted users configure via "Self-Hosted?" link on the login page. One build, 3 installers (macOS/Windows/Linux), one CI pipeline.

### 7. Packaging tool?
**Decision: electron-builder (not Electron Forge).**
Electron Forge is official but designed to manage the frontend build (Vite/webpack). We use Next.js which manages its own build. electron-builder is "bring your own build" friendly. Used by CodePilot (4,155 stars) and DarkGuy10 boilerplate (87 stars).

### 8. TypeScript compilation?
**Decision: esbuild (via custom build script).**
Used by CodePilot. Faster than `tsc`, simpler than `tsup`/`tsdown`. Only compiles 2-3 Electron files.
