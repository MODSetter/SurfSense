import { type NextRequest, NextResponse } from "next/server";

function getBackendBaseUrl() {
	const base =
		process.env.SURFSENSE_BACKEND_INTERNAL_URL ||
		// TODO: Remove FASTAPI_BACKEND_INTERNAL_URL after the post-Caddy env migration window.
		process.env.FASTAPI_BACKEND_INTERNAL_URL ||
		"http://backend:8000";
	return base.replace(/\/+$/, "");
}

export async function GET(request: NextRequest) {
	const response = await fetch(`${getBackendBaseUrl()}/verify-token`, {
		method: "GET",
		headers: {
			Authorization: request.headers.get("authorization") || "",
			"X-API-Key": request.headers.get("x-api-key") || "",
			Cookie: request.headers.get("cookie") || "",
		},
		cache: "no-store",
	});

	return new NextResponse(response.body, {
		status: response.status,
		headers: {
			"content-type": response.headers.get("content-type") || "application/json",
			"cache-control": "no-store",
		},
	});
}
