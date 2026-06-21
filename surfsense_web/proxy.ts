import { NextResponse, type NextRequest } from "next/server";
import { BUILD_TIME_AUTH_TYPE } from "@/lib/env-config";
import {
	RUNTIME_AUTH_TYPE_COOKIE_NAME,
	resolveRuntimeAuthUiMode,
} from "@/lib/runtime-auth-config";

export function proxy(request: NextRequest) {
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
