import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test features/downloads/install-script-redirects.test.ts

// The matcher Next's server resolves `redirects()` with, called with its options, so these
// assertions cannot drift from runtime behaviour.
import { getPathMatch } from "next/dist/shared/lib/router/utils/path-match";
import { installScriptRedirects } from "./install-script-redirects";

/** Applies the rules the way Next does: first match wins, or no redirect. */
function redirect(pathname: string) {
	return (
		installScriptRedirects.find(
			(rule) =>
				getPathMatch(rule.source, { strict: true, removeUnnamedParams: true })(pathname) !== false
		) ?? null
	);
}

test("each one-line install script resolves to the asset on GitHub's Latest release", () => {
	assert.equal(
		redirect("/install.sh")?.destination,
		"https://github.com/MODSetter/SurfSense/releases/latest/download/install.sh"
	);
	assert.equal(
		redirect("/install.ps1")?.destination,
		"https://github.com/MODSetter/SurfSense/releases/latest/download/install.ps1"
	);
});

test("the redirects are temporary, so no client caches a target that moves every release", () => {
	assert.ok(installScriptRedirects.length > 0);
	for (const rule of installScriptRedirects) {
		assert.equal(rule.permanent, false, rule.source);
	}
});

test("only the two script paths are redirected", () => {
	for (const pathname of [
		"/install",
		"/install.bat",
		"/downloads/install.sh",
		"/docs/install.sh",
	]) {
		assert.equal(redirect(pathname), null, pathname);
	}
});
