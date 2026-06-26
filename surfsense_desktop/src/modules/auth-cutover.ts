import { app } from 'electron';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { secretStore } from './secret-store';

const CUTOVER_FLAG_FILE = 'auth-cutover-v1.json';
const REFRESH_TOKEN_KEY = 'surfsense_refresh_token';

async function hasCompletedCutover(flagPath: string): Promise<boolean> {
  try {
    const raw = await readFile(flagPath, 'utf8');
    return JSON.parse(raw)?.complete === true;
  } catch {
    return false;
  }
}

export async function purgeLegacyAuthCutover(): Promise<void> {
  const userDataPath = app.getPath('userData');
  const flagPath = path.join(userDataPath, CUTOVER_FLAG_FILE);
  if (await hasCompletedCutover(flagPath)) return;

  await secretStore.clear(REFRESH_TOKEN_KEY);
  await mkdir(userDataPath, { recursive: true });
  await writeFile(
    flagPath,
    JSON.stringify({ complete: true, completedAt: new Date().toISOString() }),
    { mode: 0o600 }
  );
}
