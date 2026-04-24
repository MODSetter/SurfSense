/**
 * node-mac-permissions is macOS-only; electron-rebuild would still compile it on Linux/Windows
 * (missing `make`, wrong platform). We skip rebuild there.
 */
import { existsSync } from 'fs';
import { spawnSync } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

if (process.platform !== 'darwin') {
  console.log('[surfsense-desktop] Skipping electron-rebuild on non-macOS (native permissions module is darwin-only).');
  process.exit(0);
}

const bin = join(root, 'node_modules', '.bin', 'electron-rebuild');

if (!existsSync(bin)) {
  console.warn('[surfsense-desktop] electron-rebuild not found in node_modules/.bin, skipping.');
  process.exit(0);
}

const result = spawnSync(bin, [], { cwd: root, stdio: 'inherit' });
process.exit(result.status === null ? 1 : result.status);
