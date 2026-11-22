import type { PersonlessEvent } from "../personless-capture";
import { requestCountry } from "../request-country";
import { readTextWithin } from "./read-text-within";
import { usageEventProperties } from "./usage-event-properties";
import { usageReportSchema } from "./usage-report-schema";

export type UsageReportDeps = {
	record: (event: PersonlessEvent) => void;
};

// The contract's cap; a real report is well under 1 KB.
const MAX_REPORT_BYTES = 4096;

function reply(status: number, error?: string): Response {
	if (!error) return new Response(null, { status, headers: { "Cache-Control": "no-store" } });
	return Response.json({ error }, { status, headers: { "Cache-Control": "no-store" } });
}

function isJsonContentType(contentType: string | null): boolean {
	return contentType?.split(";")[0].trim().toLowerCase() === "application/json";
}

/**
 * POST /api/usage (docs/contracts/05-desktop-telemetry.md, part B). Records
 * only a report that passes the schema exactly. Reads only the body and the
 * country header: never the address, the User-Agent or a cookie.
 */
export async function receiveUsageReport(
	request: Request,
	deps: UsageReportDeps
): Promise<Response> {
	if (!isJsonContentType(request.headers.get("content-type"))) {
		return reply(415, "content_type_must_be_json");
	}

	let body: unknown;
	try {
		const text = await readTextWithin(request, MAX_REPORT_BYTES);
		if (text === null) return reply(413, "report_too_large");
		body = JSON.parse(text);
	} catch {
		return reply(400, "invalid_json");
	}

	const report = usageReportSchema.safeParse(body);
	if (!report.success) return reply(400, "invalid_report");

	deps.record({
		event: "desktop_usage_report",
		properties: usageEventProperties(report.data, requestCountry(request.headers)),
	});
	return reply(204);
}
