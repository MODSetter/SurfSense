import { randomUUID } from "node:crypto";
import type { EventMessage } from "posthog-node";
import PostHogClient from "@/features/analytics/posthog-server";
import type { DownloadSource } from "./installer-request";

export type InstallerDownload = {
	platform: string;
	src: DownloadSource;
	version: string;
	country: string | null;
};

/**
 * One personless `installer_download`: a fresh id per event and no person
 * profile, with no visitor IP, cookie id or user agent, so a download cannot
 * be joined to a visitor.
 */
export function installerDownloadMessage(
	download: InstallerDownload,
	eventId: string = randomUUID()
): EventMessage {
	return {
		distinctId: eventId,
		event: "installer_download",
		properties: {
			platform: download.platform,
			src: download.src,
			version: download.version,
			...(download.country ? { country: download.country } : {}),
			$process_person_profile: false,
		},
		disableGeoip: true,
	};
}

/**
 * Awaited inside `after()`, so the event is sent before the function ends.
 * Never throws: analytics must not cost anyone a download.
 */
export async function recordInstallerDownload(download: InstallerDownload): Promise<void> {
	try {
		await PostHogClient().captureImmediate(installerDownloadMessage(download));
	} catch {
		// No key on this deployment, or PostHog unreachable.
	}
}
