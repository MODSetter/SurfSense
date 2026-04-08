import path from 'path';
import { app } from 'electron';
import { getPort } from 'get-port-please';

const isDev = !app.isPackaged;
let serverPort = 3000;

export function getServerPort(): number {
  return serverPort;
}

function getStandalonePath(): string {
  if (isDev) {
    return path.join(__dirname, '..', '..', 'surfsense_web', '.next', 'standalone', 'surfsense_web');
  }
  return path.join(process.resourcesPath, 'standalone');
}

async function waitForServer(url: string, maxRetries = 60): Promise<boolean> {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const res = await fetch(url);
      if (res.ok || res.status === 404 || res.status === 500) return true;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

export async function startNextServer(): Promise<void> {
  if (isDev) return;

  serverPort = await getPort({ port: 3000, portRange: [30_011, 50_000] });
  console.log(`Selected port ${serverPort}`);

  const standalonePath = getStandalonePath();
  const serverScript = path.join(standalonePath, 'server.js');

  process.env.PORT = String(serverPort);
  process.env.HOSTNAME = '0.0.0.0';
  process.env.NODE_ENV = 'production';
  process.chdir(standalonePath);

  require(serverScript);

  const ready = await waitForServer(`http://localhost:${serverPort}`);
  if (!ready) {
    throw new Error('Next.js server failed to start within 30 s');
  }
  console.log(`Next.js server ready on port ${serverPort}`);
}
