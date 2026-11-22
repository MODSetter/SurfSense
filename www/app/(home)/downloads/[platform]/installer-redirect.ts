import { type NextRequest, NextResponse } from "next/server";
import { isAutomatedFetch } from "./automated-fetch";
import { installerLocation } from "./installer-location";
import { countryFromHeader, readInstallerRequest } from "./installer-request";
import type { PublishedInstallers } from "./published-installers";
import type { InstallerDownload } from "./record-installer-download";

type Context = { params: Promise<{ platform: string }> };

type Handler = (request: NextRequest, context: Context) => Promise<NextResponse>;

/** What the redirect needs from outside, so a test can stand in for GitHub, PostHog and Next. */
export type InstallerRedirectDeps = {
	publishedInstallers: () => Promise<PublishedInstallers | null>;
	recordDownload: (download: InstallerDownload) => Promise<void>;
	/** Next's `after()`: the count is sent once the redirect is, inside the same function. */
	afterResponse: (task: () => Promise<void>) => void;
};

function redirectTo(location: string | URL): NextResponse {
	const response = NextResponse.redirect(location, 302);
	response.headers.set("Cache-Control", "no-store");
	return response;
}

/**
 * GET counts a download, HEAD never does: link checkers and mail scanners send
 * HEAD, and nobody downloads with one. Neither answer waits on analytics.
 */
export function installerRedirect(deps: InstallerRedirectDeps): { GET: Handler; HEAD: Handler } {
	async function locate(request: NextRequest, { params }: Context) {
		const target = readInstallerRequest((await params).platform, request.nextUrl.searchParams);
		if (!target) return null;
		const published = await deps.publishedInstallers().catch(() => null);
		return { target, location: installerLocation(target, published) };
	}

	async function GET(request: NextRequest, context: Context): Promise<NextResponse> {
		const found = await locate(request, context);
		if (!found) return redirectTo(new URL("/downloads", request.url));

		if (!isAutomatedFetch(request.headers.get("user-agent"))) {
			const download: InstallerDownload = {
				platform: found.target.platform,
				src: found.target.src,
				version: found.location.version,
				country: countryFromHeader(request.headers.get("x-vercel-ip-country")),
			};
			try {
				deps.afterResponse(() => deps.recordDownload(download));
			} catch {
				// The redirect matters more than the count.
			}
		}

		return redirectTo(found.location.url);
	}

	async function HEAD(request: NextRequest, context: Context): Promise<NextResponse> {
		const found = await locate(request, context);
		return redirectTo(found ? found.location.url : new URL("/downloads", request.url));
	}

	return { GET, HEAD };
}
