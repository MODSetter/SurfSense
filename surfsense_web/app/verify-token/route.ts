import { type NextRequest, NextResponse } from "next/server";

const backendBaseUrl = (process.env.INTERNAL_FASTAPI_BACKEND_URL || "http://backend:8000").replace(
	/\/+$/,
	""
);

export async function GET(request: NextRequest) {
	const response = await fetch(`${backendBaseUrl}/verify-token`, {
		method: "GET",
		headers: {
			Authorization: request.headers.get("authorization") || "",
			"X-API-Key": request.headers.get("x-api-key") || "",
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
