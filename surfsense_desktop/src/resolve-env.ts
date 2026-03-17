// TODO: Placeholders are gone after the first run. Self-hosted users
// cannot change their backend URL without reinstalling.

import fs from 'fs';
import path from 'path';

const DEFAULTS: Record<string, string> = {
  __NEXT_PUBLIC_FASTAPI_BACKEND_URL__: 'http://localhost:8000',
  __NEXT_PUBLIC_FASTAPI_BACKEND_AUTH_TYPE__: 'LOCAL',
  __NEXT_PUBLIC_ETL_SERVICE__: 'DOCLING',
  __NEXT_PUBLIC_ELECTRIC_URL__: 'http://localhost:5133',
  __NEXT_PUBLIC_ELECTRIC_AUTH_MODE__: 'insecure',
  __NEXT_PUBLIC_DEPLOYMENT_MODE__: 'self-hosted',
};

function walk(dir: string, replacements: [string, string][]) {
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, replacements);
    } else if (entry.name.endsWith('.js')) {
      let content = fs.readFileSync(full, 'utf8');
      let changed = false;
      for (const [placeholder, value] of replacements) {
        if (content.includes(placeholder)) {
          content = content.replaceAll(placeholder, value);
          changed = true;
        }
      }
      if (changed) {
        fs.writeFileSync(full, content);
      }
    }
  }
}

export function resolveEnv(standalonePath: string, overrides?: Record<string, string>) {
  const replacements: [string, string][] = Object.entries(DEFAULTS).map(
    ([placeholder, defaultValue]) => {
      const envKey = placeholder.replace(/^__|__$/g, '');
      const value = overrides?.[envKey] ?? process.env[envKey] ?? defaultValue;
      return [placeholder, value];
    }
  );

  console.log('[resolve-env] Replacing placeholders in standalone build:');
  for (const [placeholder, value] of replacements) {
    console.log(`  ${placeholder} -> ${value}`);
  }

  walk(path.join(standalonePath, '.next'), replacements);

  const serverJs = path.join(standalonePath, 'server.js');
  if (fs.existsSync(serverJs)) {
    let content = fs.readFileSync(serverJs, 'utf8');
    for (const [placeholder, value] of replacements) {
      if (content.includes(placeholder)) {
        content = content.replaceAll(placeholder, value);
      }
    }
    fs.writeFileSync(serverJs, content);
  }
}
