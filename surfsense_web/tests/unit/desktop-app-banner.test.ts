import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test tests/unit/desktop-app-banner.test.ts

import { bannerPlacement } from "../../components/desktop-app-banner/banner-placement";

test("sign-in pages always show it, with no way to dismiss it", () => {
	for (const pathname of ["/login", "/register", "/login?registered=true"]) {
		assert.equal(bannerPlacement(pathname), "fixed", pathname);
	}
});

test("the app shows it and lets the user dismiss it", () => {
	for (const pathname of ["/", "/dashboard", "/dashboard/12/new-chat", "/invite/abc"]) {
		assert.equal(bannerPlacement(pathname), "dismissible", pathname);
	}
});

test("shared chats and the old desktop handoff never show it", () => {
	for (const pathname of ["/public/token-123", "/desktop/login", "/desktop/permissions"]) {
		assert.equal(bannerPlacement(pathname), "hidden", pathname);
	}
});
