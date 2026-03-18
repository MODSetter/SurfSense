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

**Step 3** — Package into a distributable:

```bash
pnpm dist:mac      # macOS (.dmg + .zip)
pnpm dist:win      # Windows (.exe)
pnpm dist:linux    # Linux (.deb + .AppImage)
```

**Step 4** — Find the output:

```bash
ls release/
```
