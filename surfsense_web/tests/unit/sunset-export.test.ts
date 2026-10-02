import assert from "node:assert/strict";
import test from "node:test";
import { exportWaitMessage, SLOW_EXPORT_AFTER_SECONDS } from "@/app/(home)/sunset/export-wait";
import { filenameFromDisposition } from "@/app/(home)/sunset/sunset-export";
import { isPublicRoute } from "@/lib/auth-utils";

test("sunset is a public route so Zero does not blank the page", () => {
	assert.equal(isPublicRoute("/sunset"), true);
});

test("export filename comes from Content-Disposition", () => {
	assert.equal(
		filenameFromDisposition('attachment; filename="surfsense-export.zip"'),
		"surfsense-export.zip"
	);
	assert.equal(filenameFromDisposition(null), "surfsense-export.zip");
});

test("a quick export says nothing while it builds", () => {
	assert.equal(exportWaitMessage(0), null);
	assert.equal(exportWaitMessage(SLOW_EXPORT_AFTER_SECONDS - 1), null);
});

test("a slow export says it is still working, for how long, and to keep the tab open", () => {
	const message = exportWaitMessage(SLOW_EXPORT_AFTER_SECONDS);
	assert.ok(message);
	assert.match(message, /Still building your export \(10 s so far\)/);
	assert.match(message, /Keep this tab open/);
});

test("the wait is given in minutes once it is that long", () => {
	assert.match(exportWaitMessage(60) ?? "", /\(1 min so far\)/);
	assert.match(exportWaitMessage(95.7) ?? "", /\(1 min 35 s so far\)/);
});
