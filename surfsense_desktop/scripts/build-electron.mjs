import { build } from 'esbuild';
import fs from 'fs';
import path from 'path';

/**
 * electron-builder cannot follow symlinks when packaging into ASAR.
 * Next.js standalone output contains symlinks in node_modules that
 * must be replaced with real copies before packaging.
 * Pattern from CodePilot (github.com/op7418/CodePilot).
 */
function resolveStandaloneSymlinks() {
  const standaloneModules = path.join(
    '..', 'surfsense_web', '.next', 'standalone', 'surfsense_web', 'node_modules'
  );
  if (!fs.existsSync(standaloneModules)) return;

  const entries = fs.readdirSync(standaloneModules);
  for (const entry of entries) {
    const fullPath = path.join(standaloneModules, entry);
    const stat = fs.lstatSync(fullPath);
    if (stat.isSymbolicLink()) {
      const target = fs.readlinkSync(fullPath);
      const resolved = path.resolve(standaloneModules, target);
      if (fs.existsSync(resolved)) {
        fs.rmSync(fullPath, { recursive: true, force: true });
        fs.cpSync(resolved, fullPath, { recursive: true });
        console.log(`Resolved symlink: ${entry} -> ${target}`);
      }
    }
  }
}

async function buildElectron() {
  if (fs.existsSync('dist')) {
    fs.rmSync('dist', { recursive: true });
    console.log('Cleaned dist/');
  }
  fs.mkdirSync('dist', { recursive: true });

  const shared = {
    bundle: true,
    platform: 'node',
    target: 'node18',
    external: ['electron'],
    sourcemap: true,
    minify: false,
  };

  await build({
    ...shared,
    entryPoints: ['src/main.ts'],
    outfile: 'dist/main.js',
  });

  await build({
    ...shared,
    entryPoints: ['src/preload.ts'],
    outfile: 'dist/preload.js',
  });

  console.log('Electron build complete');
  resolveStandaloneSymlinks();
}

buildElectron().catch((err) => {
  console.error(err);
  process.exit(1);
});
