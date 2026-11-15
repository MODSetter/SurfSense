/**
 * Starts a throwaway SurfSense for the captures: the sidecars Electron boots,
 * on a data folder of its own, and the built renderer on a local port.
 *
 * Not `headless/main.ts`: that entry is the Docker image's, and it sets
 * `HF_HUB_OFFLINE` and `SURFSENSE_LOCAL_RUNTIME=docker`, which block model
 * downloads and change what the API answers. This passes the context Electron's
 * dev build passes (`electron/src/main/index.ts`), so the guides show the desktop.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { resolveSecret } from "../../../../surfsense_local/headless/secret.ts";
import { bootSidecars } from "../../../../surfsense_local/sidecars/boot.ts";
import { stopAll } from "../../../../surfsense_local/sidecars/supervisor.ts";

const REPO = fileURLToPath(new URL("../../../../", import.meta.url));
const LOCAL = join(REPO, "surfsense_local");
const FRONTEND = join(LOCAL, "frontend");

/** A checkout stages its runtimes and bundled models itself; a worktree can borrow another's. */
function folders(env) {
	const runtimes = env.GUIDES_RUNTIMES_DIR || join(LOCAL, "electron");
	return {
		backendDir: env.GUIDES_BACKEND_DIR || join(LOCAL, "backend"),
		modelsDir: env.GUIDES_MODELS_DIR || join(LOCAL, "backend", "models"),
		runtimes,
	};
}

async function waitForPage(url, timeoutMs) {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		try {
			const response = await fetch(url);
			if (response.ok) return;
		} catch {
			// Not listening yet.
		}
		await new Promise((resolve) => setTimeout(resolve, 250));
	}
	throw new Error(`${url} did not answer within ${timeoutMs / 1000} s`);
}

/** The renderer as packaged, served by `vite preview`, which needs `pnpm build` first. */
async function serveRenderer(port) {
	if (!existsSync(join(FRONTEND, "dist", "index.html"))) {
		throw new Error(
			"Build the renderer first: in surfsense_local/frontend, run `pnpm translations` and `vite build`."
		);
	}
	const vite = join(FRONTEND, "node_modules", "vite", "bin", "vite.js");
	const child = spawn(
		process.execPath,
		[vite, "preview", "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
		{ cwd: FRONTEND, stdio: ["ignore", "ignore", "inherit"] }
	);
	const url = `http://127.0.0.1:${port}/`;
	await waitForPage(url, 30_000);
	return { url, stop: () => child.kill() };
}

/**
 * @param {{ dataDir: string, rendererPort?: number, env?: NodeJS.ProcessEnv }} options
 * @returns {Promise<{ apiUrl: string, appUrl: string, dataDir: string, stop: () => Promise<void> }>}
 */
export async function bootApp({ dataDir, rendererPort = 5199, env = process.env }) {
	const { backendDir, modelsDir, runtimes } = folders(env);
	mkdirSync(dataDir, { recursive: true });
	const booted = await bootSidecars(
		{
			packaged: false,
			backendDir,
			binariesDir: LOCAL,
			dataDir,
			// Per data folder, like an install's: a copied base state keeps its stored keys readable.
			secret: resolveSecret({}, dataDir),
			modelsDir,
			llamacppBinariesDir: join(runtimes, "llamacpp"),
			audioBinariesDir: join(runtimes, "audiocpp"),
			sdcppBinariesDir: join(runtimes, "sdcpp"),
			opencodeBinariesDir: join(runtimes, "opencode"),
		},
		(name, code) => console.error(`[guides] ${name} exited (code=${code})`)
	);
	const stopSidecars = async () => {
		booted.stopWatching();
		await stopAll(booted.sidecars);
	};
	try {
		await booted.waitHealthy();
	} catch (error) {
		await stopSidecars();
		throw error;
	}
	const renderer = await serveRenderer(rendererPort).catch(async (error) => {
		await stopSidecars();
		throw error;
	});
	return {
		apiUrl: booted.apiUrl,
		appUrl: renderer.url,
		dataDir,
		stop: async () => {
			renderer.stop();
			await stopSidecars();
		},
	};
}
