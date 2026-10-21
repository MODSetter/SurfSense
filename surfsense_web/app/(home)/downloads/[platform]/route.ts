import { after, type NextRequest, NextResponse } from "next/server";
import { isAutomatedFetch } from "./automated-fetch";
import { countryFromHeader, readInstallerRequest } from "./installer-request";
import { recordInstallerDownload } from "./record-installer-download";

/**
 * `/downloads/<platform>?src=&v=`: count the download, then 302 to the
 * installer on GitHub. The bytes never pass through here (a function response
 * is capped far below an installer's size). Every link outside the app points
 * here: the /downloads grid, the READMEs and the licence email.
 */

type Context = { params: Promise<{ platform: string }> };

function redirectTo(location: string | URL): NextResponse {
	const response = NextResponse.redirect(location, 302);
	response.headers.set("Cache-Control", "no-store");
	return response;
}

export async function GET(request: NextRequest, { params }: Context): Promise<NextResponse> {
	const target = readInstallerRequest((await params).platform, request.nextUrl.searchParams);
	if (!target) return redirectTo(new URL("/downloads", request.url));

	if (!isAutomatedFetch(request.headers.get("user-agent"))) {
		const download = {
			platform: target.platform,
			src: target.src,
			version: target.version,
			country: countryFromHeader(request.headers.get("x-vercel-ip-country")),
		};
		try {
			after(() => recordInstallerDownload(download));
		} catch {
			// Outside a request scope; the redirect matters more than the count.
		}
	}

	return redirectTo(target.assetUrl);
}

/** Link checkers and mail scanners send HEAD; nobody downloads with one. */
export async function HEAD(request: NextRequest, { params }: Context): Promise<NextResponse> {
	const target = readInstallerRequest((await params).platform, request.nextUrl.searchParams);
	return redirectTo(target ? target.assetUrl : new URL("/downloads", request.url));
}
