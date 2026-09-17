import { type NextRequest, NextResponse } from "next/server";
import { BUILD_TIME_AUTH_TYPE } from "@/lib/env-config";
import { RUNTIME_AUTH_TYPE_COOKIE_NAME, resolveRuntimeAuthUiMode } from "@/lib/runtime-auth-config";
import { shouldRedirectToSunset } from "@/lib/sunset";

export function proxy(request: NextRequest) {
	// Read per request, so the hosted wind-down is a flag change rather than a
	// redeploy. Unset -- every self-host install -- costs one set lookup.
	if (shouldRedirectToSunset(request.nextUrl.pathname, process.env.SUNSET_MODE)) {
		const destination = request.nextUrl.clone();
		destination.pathname = "/sunset";
		destination.search = "";
		return NextResponse.redirect(destination);
	}

	const response = NextResponse.next();
	const authType = resolveRuntimeAuthUiMode(process.env.AUTH_TYPE, BUILD_TIME_AUTH_TYPE);

	response.cookies.set(RUNTIME_AUTH_TYPE_COOKIE_NAME, authType, {
		path: "/",
		maxAge: 60 * 60 * 24 * 365,
		sameSite: "lax",
		secure: request.nextUrl.protocol === "https:",
	});

	return response;
}

export const config = {
	matcher: ["/((?!api|auth|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
