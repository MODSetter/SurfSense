/**
 * Self-check: the app must run on ONE jotai store.
 *
 * Regression guard for the "screenshot never sent" bug: wrapping the tree in
 * jotai-tanstack-query's QueryClientAtomProvider mounted a second jotai
 * <Provider> store, so hook writes (pending screenshot data URLs, mentions)
 * were invisible to the chat stream engine's getDefaultStore() reads and
 * user_images arrived empty at the backend.
 *
 * Run: pnpm exec tsx lib/query-client/query-client.provider.check.tsx
 */
import assert from "node:assert";
import { getDefaultStore, useStore } from "jotai";
import { queryClientAtom } from "jotai-tanstack-query";
import { renderToString } from "react-dom/server";
import { ReactQueryClientProvider } from "./query-client.provider";

let seenStore: unknown;
function Probe() {
	seenStore = useStore();
	return null;
}

renderToString(
	<ReactQueryClientProvider>
		<Probe />
	</ReactQueryClientProvider>
);

assert.strictEqual(
	seenStore,
	getDefaultStore(),
	"jotai hooks inside ReactQueryClientProvider must use the default store " +
		"(a nested jotai <Provider> would hide composer atom writes from the chat engine)"
);
assert.ok(
	getDefaultStore().get(queryClientAtom),
	"queryClientAtom must be hydrated into the default store"
);
console.log("OK: single jotai store, queryClientAtom hydrated");
