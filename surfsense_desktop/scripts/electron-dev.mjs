/**
 * Linux dev: (1) ELECTRON_DISABLE_SANDBOX before start — setuid chrome-sandbox in node_modules.
 * (2) --ozone-platform=x11 — use X11 via XWayland so global shortcuts / GPU warnings match many
 *     Linux Electron setups better than native Wayland. Set SURFSENSE_ELECTRON_WAYLAND=1 to skip (2).
 * Packaged apps are not launched through this script.
 */
import { spawnSync } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const cli = join(root, 'node_modules', 'electron', 'cli.js');

const env = { ...process.env };
const args = [cli, '.'];
if (process.platform === 'linux') {
  env.ELECTRON_DISABLE_SANDBOX = '1';
  if (env.SURFSENSE_ELECTRON_WAYLAND !== '1') {
    args.push('--ozone-platform=x11');
  }
}

const r = spawnSync(process.execPath, args, { cwd: root, env, stdio: 'inherit' });
process.exit(r.status === null ? 1 : r.status ?? 0);
