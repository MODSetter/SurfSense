import { readUpdateCheckDimensions } from "../desktop-dimensions";
import type { PersonlessEvent } from "../personless-capture";
import { requestCountry } from "../request-country";
import { isChannelFile } from "./channel-files";
import { type FetchManifest, fetchLatestGithubManifest } from "./latest-github-manifest";
import { pinManifestToRelease } from "./pin-manifest-to-release";

export type UpdateFeedDeps = {
	fetchManifest: FetchManifest;
	record: (event: PersonlessEvent) => void;
};

const NO_STORE = { "Cache-Control": "no-store" };

/**
 * GET /api/updates/<file> (docs/contracts/05-desktop-telemetry.md, part A).
 * Every failure is a 502, which sends the app to GitHub directly, so this
 * route can be down or wrong without blocking an update. Reads only the
 * X-SurfSense-* headers and the country header: never the address or the
 * User-Agent.
 */
export async function serveUpdateManifest(
	request: Request,
	file: string,
	deps: UpdateFeedDeps
): Promise<Response> {
	if (!isChannelFile(file)) return new Response("Not found\n", { status: 404, headers: NO_STORE });

	// Counted whatever GitHub answers: the app checked either way. Next answers
	// HEAD with this handler too, but the app only GETs, so a HEAD is a monitor
	// or a scanner and is not an update check.
	if (request.method !== "HEAD") {
		deps.record({
			event: "desktop_update_check",
			properties: {
				file,
				...readUpdateCheckDimensions(request.headers),
				country: requestCountry(request.headers),
			},
		});
	}

	try {
		const manifest = pinManifestToRelease(
			await fetchLatestGithubManifest(file, deps.fetchManifest)
		);
		return new Response(manifest, {
			status: 200,
			headers: { "Content-Type": "text/yaml", ...NO_STORE },
		});
	} catch (error) {
		console.warn(`[updates] ${file} not served: ${error instanceof Error ? error.message : error}`);
		return new Response("Bad gateway\n", { status: 502, headers: NO_STORE });
	}
}
