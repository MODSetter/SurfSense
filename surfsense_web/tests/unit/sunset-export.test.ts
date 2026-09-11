import assert from "node:assert/strict";
import test from "node:test";
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
