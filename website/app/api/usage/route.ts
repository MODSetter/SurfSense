import { recordAfterResponse } from "@/features/desktop-telemetry/record-after-response";
import { receiveUsageReport } from "@/features/desktop-telemetry/usage-report/receive-usage-report";

export const dynamic = "force-dynamic";

/** Opt-in usage reports at usage.surfsense.com (docs/contracts/05-desktop-telemetry.md). */
export async function POST(request: Request) {
	return receiveUsageReport(request, { record: recordAfterResponse });
}
