import {
	INSTALLER_FILES,
	installerAssetUrl,
	latestInstallerUrl,
} from "@/features/downloads/app-release";
import type { InstallerRequest } from "./installer-request";
import type { PublishedInstallers } from "./published-installers";

/** Recorded as the version when the redirect could not name the build. */
export const LATEST_VERSION = "latest";

export type InstallerLocation = { version: string; url: string };

/**
 * The asked-for build when GitHub serves it, else Latest. A new pin deploys
 * while its release is still a draft, and a tag may never have been published;
 * either way the link must still reach an installer.
 */
export function installerLocation(
	request: InstallerRequest,
	published: PublishedInstallers | null
): InstallerLocation {
	const file = INSTALLER_FILES[request.platform];
	if (published?.get(`v${request.version}`)?.has(file)) {
		return {
			version: request.version,
			url: installerAssetUrl(request.version, request.platform),
		};
	}
	return { version: LATEST_VERSION, url: latestInstallerUrl(request.platform) };
}
