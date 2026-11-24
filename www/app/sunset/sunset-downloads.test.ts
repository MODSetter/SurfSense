import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test app/sunset/sunset-downloads.test.ts

import { readInstallerRequest } from "@/app/(home)/downloads/[platform]/installer-request";
import { INSTALLER_FILES } from "@/features/downloads/app-release";
import { SUNSET_DOWNLOADS, SUNSET_OTHER_DOWNLOADS_URL } from "./sunset-downloads";

test("the sunset page offers every installer /downloads/<platform> serves", () => {
	assert.deepEqual(
		SUNSET_DOWNLOADS.map((download) => download.platform).sort(),
		Object.keys(INSTALLER_FILES).sort()
	);
});

test("each button is an absolute www link counted as a move from the legacy app", () => {
	for (const download of SUNSET_DOWNLOADS) {
		const url = new URL(download.href);
		assert.equal(url.origin, "https://www.surfsense.com");
		assert.equal(url.pathname, `/downloads/${download.platform}`);
		const request = readInstallerRequest(download.platform, url.searchParams);
		assert.equal(request?.src, "legacy", download.href);
	}
	assert.equal(new URL(SUNSET_OTHER_DOWNLOADS_URL).pathname, "/downloads");
});
