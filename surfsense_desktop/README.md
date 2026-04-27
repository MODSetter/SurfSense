# SurfSense Desktop

Electron wrapper around the SurfSense web app. Packages the Next.js standalone build into a native desktop application with OAuth support, deep linking, and system browser integration.

## Prerequisites

- Node.js 18+
- pnpm 10+
- The `surfsense_web` project dependencies installed (`pnpm install` in `surfsense_web/`)

## Development

```bash
pnpm install
pnpm dev
```

This starts the Next.js dev server and Electron concurrently. Hot reload works — edit the web app and changes appear immediately.

On **Linux**, `pnpm dev` runs Electron through `scripts/electron-dev.mjs`: it sets `ELECTRON_DISABLE_SANDBOX=1` for the sandbox issue and passes **`--ozone-platform=x11`** (XWayland) unless **`SURFSENSE_ELECTRON_WAYLAND=1`** is set, so dev tends to behave closer to X11 for shortcuts and Ozone. Packaged Linux builds are unchanged.

## Configuration

Two `.env` files control the build:

**`surfsense_web/.env`** — Next.js environment variables baked into the frontend at build time:

**`surfsense_desktop/.env`** — Electron-specific configuration:

Set these before building.

## Build & Package

**Step 1** — Build the Next.js standalone output:

```bash
cd ../surfsense_web
pnpm build
```

**Step 2** — Compile Electron and prepare the standalone output:

```bash
cd ../surfsense_desktop
pnpm build
```

**Step 3** — Package into a distributable (after steps 1–2):

```bash
pnpm dist:mac      # macOS (.dmg + .zip)
pnpm dist:win      # Windows (.exe)
pnpm dist:linux    # Linux (.deb + .AppImage)
pnpm pack:dir      # optional: unpacked app only → release/… (run that binary yourself)
```

**Step 4** — Find the output:

```bash
ls release/
```
