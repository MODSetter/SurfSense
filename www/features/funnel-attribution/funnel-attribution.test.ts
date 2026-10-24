import assert from "node:assert/strict";
import test from "node:test";

// Run with: pnpm exec tsx --test features/funnel-attribution/funnel-attribution.test.ts

import {
	channelFor,
	DIRECT_CHANNEL,
	referrerDomain,
	toChannelTag,
	touchFromUrl,
} from "@/features/funnel-attribution/channel-tag";
import { trialOutcome } from "@/features/funnel-attribution/trial-outcome";

const OWN = "www.surfsense.com";

test("a channel tag is lowercase [a-z0-9_-], at most 40 characters", () => {
	assert.equal(toChannelTag("Hacker News"), "hacker-news");
	assert.equal(toChannelTag("news.ycombinator.com"), "news-ycombinator-com");
	assert.equal(toChannelTag("  --Reddit!!  "), "reddit");
	assert.equal(toChannelTag("a".repeat(60)), "a".repeat(40));
	// Truncation never leaves a trailing separator behind.
	assert.equal(toChannelTag(`${"a".repeat(39)} b`), "a".repeat(39));
	for (const tag of ["Hacker News", "x".repeat(99), "ünïcödé", "ref:hn"]) {
		assert.match(toChannelTag(tag) ?? "", /^[a-z0-9_-]{1,40}$/);
	}
});

test("nothing usable is no tag, not an empty one", () => {
	for (const raw of [null, undefined, "", "   ", "!!!", "日本"]) {
		assert.equal(toChannelTag(raw), null, String(raw));
	}
});

test("our own pages and non-URLs are not referrers", () => {
	assert.equal(referrerDomain("https://www.google.com/search?q=x", OWN), "google.com");
	assert.equal(referrerDomain("https://www.surfsense.com/pricing", OWN), null);
	assert.equal(referrerDomain("https://docs.surfsense.com/", OWN), null);
	assert.equal(referrerDomain("http://localhost:3000/", "localhost"), null);
	assert.equal(referrerDomain("$direct", OWN), null);
	assert.equal(referrerDomain("", OWN), null);
});

test("a ref code beats utm_source, and any tag beats a referrer", () => {
	assert.equal(
		channelFor([touchFromUrl("https://www.surfsense.com/?ref=HN&utm_source=x")], OWN),
		"hn"
	);
	assert.equal(
		channelFor(
			[
				touchFromUrl("https://www.surfsense.com/", "https://www.google.com/"),
				touchFromUrl("https://www.surfsense.com/pricing?utm_source=newsletter"),
			],
			OWN
		),
		"newsletter"
	);
});

test("the earliest touch wins among tags, then among referrers", () => {
	const touches = [
		touchFromUrl("https://www.surfsense.com/?ref=launch", "https://news.ycombinator.com/"),
		{ ref: "later" },
	];
	assert.equal(channelFor(touches, OWN), "launch");
	assert.equal(
		channelFor(
			[
				touchFromUrl("https://www.surfsense.com/", "https://github.com/MODSetter/SurfSense"),
				touchFromUrl("https://www.surfsense.com/pricing", "https://www.bing.com/"),
			],
			OWN
		),
		"github-com"
	);
});

test("no tag and no outside referrer is direct", () => {
	assert.equal(channelFor([], OWN), DIRECT_CHANNEL);
	assert.equal(
		channelFor(
			[touchFromUrl("https://www.surfsense.com/pricing", "https://www.surfsense.com/")],
			OWN
		),
		DIRECT_CHANNEL
	);
	assert.equal(channelFor([touchFromUrl("not a url", "also not")], OWN), DIRECT_CHANNEL);
});

test("each trial answer maps to one outcome", () => {
	assert.equal(trialOutcome(200), "sent");
	assert.equal(trialOutcome(409), "already_claimed");
	assert.equal(trialOutcome(400), "refused");
	for (const status of [404, 422, 429, 500, 503, null]) {
		assert.equal(trialOutcome(status), "error", String(status));
	}
});
