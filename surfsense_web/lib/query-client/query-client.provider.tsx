"use client";
import { QueryClientAtomProvider } from "jotai-tanstack-query/react";
import dynamic from "next/dynamic";
import { queryClient } from "./client";

const ReactQueryDevtools = dynamic(
	() => import("@tanstack/react-query-devtools").then((m) => ({ default: m.ReactQueryDevtools })),
	{ ssr: false }
);

export function ReactQueryClientProvider({ children }: { children: React.ReactNode }) {
	return (
		<QueryClientAtomProvider client={queryClient}>
			{children}
			{process.env.NODE_ENV === "development" && <ReactQueryDevtools initialIsOpen={false} />}
		</QueryClientAtomProvider>
	);
}
