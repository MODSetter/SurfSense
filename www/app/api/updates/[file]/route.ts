import { recordAfterResponse } from "@/features/desktop-telemetry/record-after-response";
import { serveUpdateManifest } from "@/features/desktop-telemetry/update-feed/serve-update-manifest";

// Each check must reach the handler to be counted. The GitHub fetch inside
// keeps its own 15-minute cache.
export const dynamic = "force-dynamic";

/** The desktop update feed at updates.surfsense.com (docs/contracts/05-desktop-telemetry.md). */
export async function GET(request: Request, { params }: { params: Promise<{ file: string }> }) {
	const { file } = await params;
	return serveUpdateManifest(request, file, { fetchManifest: fetch, record: recordAfterResponse });
}
