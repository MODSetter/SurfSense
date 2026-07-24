"use client";
import { QueryClientProvider } from "@tanstack/react-query";
import { getDefaultStore } from "jotai";
import { queryClientAtom } from "jotai-tanstack-query";
import dynamic from "next/dynamic";
import { queryClient } from "./client";

const ReactQueryDevtools = dynamic(
	() => import("@tanstack/react-query-devtools").then((m) => ({ default: m.ReactQueryDevtools })),
	{ ssr: false }
);

// Do NOT use jotai-tanstack-query's QueryClientAtomProvider here: it mounts
// its own jotai <Provider>, which creates a SECOND jotai store for the React
// tree. Hook writes (e.g. pending screenshot data URLs, @-mentions) then land
// in that provider store while the chat stream engine reads via
// getDefaultStore(), so user_images silently arrived empty at the backend.
// Instead, keep the whole app on the one default store and hydrate the
// query-client atom into it directly.
getDefaultStore().set(queryClientAtom, queryClient);

export function ReactQueryClientProvider({ children }: { children: React.ReactNode }) {
	return (
		<QueryClientProvider client={queryClient}>
			{children}
			{process.env.NODE_ENV === "development" && <ReactQueryDevtools initialIsOpen={false} />}
		</QueryClientProvider>
	);
}
