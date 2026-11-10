/** ffmpeg from `FFMPEG` or the PATH; every guide's pictures and videos go through it. */

import { spawn } from "node:child_process";

export function runFfmpeg(args) {
	return new Promise((resolve, reject) => {
		const child = spawn(
			process.env.FFMPEG || "ffmpeg",
			["-hide_banner", "-loglevel", "error", "-y", ...args],
			{
				stdio: ["ignore", "ignore", "pipe"],
			}
		);
		let errors = "";
		child.stderr.on("data", (chunk) => {
			errors += chunk;
		});
		child.on("error", reject);
		child.on("close", (code) =>
			code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}: ${errors.trim()}`))
		);
	});
}
