import { build } from 'esbuild';
import fs from 'fs';
import path from 'path';
import dotenv from 'dotenv';

const desktopEnv = dotenv.config().parsed || {};

const STANDALONE_ROOT = path.join(
  '..', 'surfsense_web', '.next', 'standalone', 'surfsense_web'
);

/**
 * electron-builder cannot follow symlinks when packaging into ASAR.
 * Recursively walk the standalone output and replace every symlink
 * with a real copy (or remove it if the target doesn't exist).
 */
function resolveAllSymlinks(dir) {
  if (!fs.existsSync(dir)) return;

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isSymbolicLink()) {
      const target = fs.readlinkSync(full);
      const resolved = path.resolve(dir, target);
      if (fs.existsSync(resolved)) {
        fs.rmSync(full, { recursive: true, force: true });
        fs.cpSync(resolved, full, { recursive: true });
        console.log(`Resolved symlink: ${full}`);
      } else {
        fs.rmSync(full, { force: true });
        console.log(`Removed broken symlink: ${full}`);
      }
    } else if (entry.isDirectory()) {
      resolveAllSymlinks(full);
    }
  }
}

/**
 * pnpm's .pnpm/ virtual store uses symlinks for sibling dependency resolution.
 * After resolveAllSymlinks converts everything to real copies, packages can no
 * longer find their dependencies through the pnpm structure.  We flatten the
 * tree into a standard npm-like layout: every package from .pnpm/&ast;/node_modules/
 * gets hoisted to the top-level node_modules/.  This lets Node.js standard
 * module resolution find all dependencies (e.g. next → styled-jsx).
 */
function flattenPnpmStore(nodeModulesDir) {
  const pnpmDir = path.join(nodeModulesDir, '.pnpm');
  if (!fs.existsSync(pnpmDir)) return;

  console.log('Flattening pnpm store to top-level node_modules...');
  let hoisted = 0;

  for (const storePkg of fs.readdirSync(pnpmDir, { withFileTypes: true })) {
    if (!storePkg.isDirectory() || storePkg.name === 'node_modules') continue;

    const innerNM = path.join(pnpmDir, storePkg.name, 'node_modules');
    if (!fs.existsSync(innerNM)) continue;

    for (const dep of fs.readdirSync(innerNM, { withFileTypes: true })) {
      const depName = dep.name;
      // Handle scoped packages (@org/pkg)
      if (depName.startsWith('@') && dep.isDirectory()) {
        const scopeDir = path.join(innerNM, depName);
        for (const scopedPkg of fs.readdirSync(scopeDir, { withFileTypes: true })) {
          const fullName = `${depName}/${scopedPkg.name}`;
          const src = path.join(scopeDir, scopedPkg.name);
          const dest = path.join(nodeModulesDir, depName, scopedPkg.name);
          if (!fs.existsSync(dest)) {
            fs.mkdirSync(path.join(nodeModulesDir, depName), { recursive: true });
            fs.cpSync(src, dest, { recursive: true });
            hoisted++;
          }
        }
      } else if (dep.isDirectory() || dep.isFile()) {
        const dest = path.join(nodeModulesDir, depName);
        if (!fs.existsSync(dest)) {
          fs.cpSync(path.join(innerNM, depName), dest, { recursive: true });
          hoisted++;
        }
      }
    }
  }

  // Remove the .pnpm directory — no longer needed
  fs.rmSync(pnpmDir, { recursive: true, force: true });
  console.log(`Hoisted ${hoisted} packages, removed .pnpm/`);
}

function resolveStandaloneSymlinks() {
  console.log('Resolving symlinks in standalone output...');
  resolveAllSymlinks(STANDALONE_ROOT);
  flattenPnpmStore(path.join(STANDALONE_ROOT, 'node_modules'));
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
    external: ['electron', 'node-mac-permissions', 'bindings', 'file-uri-to-path'],
    sourcemap: true,
    minify: false,
    define: {
      'process.env.HOSTED_FRONTEND_URL': JSON.stringify(
        process.env.HOSTED_FRONTEND_URL || desktopEnv.HOSTED_FRONTEND_URL || 'https://surfsense.net'
      ),
    },
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
