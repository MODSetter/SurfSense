import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const HOP_BY_HOP_HEADERS = new Set([
	"connection",
	"keep-alive",
	"proxy-authenticate",
	"proxy-authorization",
	"te",
	"trailer",
	"transfer-encoding",
	"upgrade",
]);

function getBackendBaseUrl() {
	const base = process.env.FASTAPI_BACKEND_INTERNAL_URL || "http://localhost:8000";
	return base.endsWith("/") ? base.slice(0, -1) : base;
}

function toUpstreamHeaders(headers: Headers) {
	const nextHeaders = new Headers(headers);
	nextHeaders.delete("host");
	nextHeaders.delete("content-length");
	return nextHeaders;
}

function toClientHeaders(headers: Headers) {
	const nextHeaders = new Headers(headers);
	for (const header of HOP_BY_HOP_HEADERS) {
		nextHeaders.delete(header);
	}
	return nextHeaders;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
	const params = await context.params;
	const path = params.path?.join("/") || "";
	const upstreamUrl = new URL(`${getBackendBaseUrl()}/api/v1/${path}`);
	upstreamUrl.search = request.nextUrl.search;

	const hasBody = request.method !== "GET" && request.method !== "HEAD";

	const response = await fetch(upstreamUrl, {
		method: request.method,
		headers: toUpstreamHeaders(request.headers),
		body: hasBody ? request.body : undefined,
		// `duplex: "half"` is required by the Fetch spec when streaming a
		// ReadableStream as the request body. Avoids buffering uploads in heap.
		// @ts-expect-error - `duplex` is not yet in lib.dom RequestInit types.
		duplex: hasBody ? "half" : undefined,
		redirect: "manual",
	});

	return new Response(response.body, {
		status: response.status,
		statusText: response.statusText,
		headers: toClientHeaders(response.headers),
	});
}

export {
	proxy as GET,
	proxy as POST,
	proxy as PUT,
	proxy as PATCH,
	proxy as DELETE,
	proxy as OPTIONS,
	proxy as HEAD,
};
