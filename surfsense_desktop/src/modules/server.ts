import path from 'path';
import { app, utilityProcess } from 'electron';
import { getPort } from 'get-port-please';

const isDev = !app.isPackaged;
const SERVER_HOST = '127.0.0.1';
let serverPort = 3000;
let nextServerProcess: ReturnType<typeof utilityProcess.fork> | null = null;

export function getServerPort(): number {
  return serverPort;
}

export function getServerOrigin(): string {
  return `http://${SERVER_HOST}:${serverPort}`;
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

  const child = utilityProcess.fork(serverScript, [], {
    cwd: standalonePath,
    env: {
      ...process.env,
      PORT: String(serverPort),
      // Loopback bind: avoids 0.0.0.0 leaking into request.url and redirect origins.
      HOSTNAME: SERVER_HOST,
      NODE_ENV: 'production',
    },
    serviceName: 'SurfSense Next Server',
    stdio: 'pipe',
  });
  nextServerProcess = child;

  child.stdout?.on('data', (chunk) => {
    process.stdout.write(chunk);
  });
  child.stderr?.on('data', (chunk) => {
    process.stderr.write(chunk);
  });

  const handleExit = (code: number) => {
    if (nextServerProcess === child) {
      nextServerProcess = null;
    }
    console.error(`Next.js server exited with code ${code}`);
  };
  child.on('exit', handleExit);

  let startupExitHandler: ((code: number) => void) | null = null;
  const exited = new Promise<never>((_resolve, reject) => {
    startupExitHandler = (code: number) => {
      reject(new Error(`Next.js server exited before startup completed with code ${code}`));
    };
    child.once('exit', startupExitHandler);
  });

  const ready = await Promise.race([waitForServer(getServerOrigin()), exited]);
  if (startupExitHandler) {
    child.removeListener('exit', startupExitHandler);
  }
  if (!ready) {
    stopNextServer();
    throw new Error('Next.js server failed to start within 30 s');
  }
  console.log(`Next.js server ready on port ${serverPort}`);
}

export function stopNextServer(): void {
  nextServerProcess?.kill();
  nextServerProcess = null;
}
