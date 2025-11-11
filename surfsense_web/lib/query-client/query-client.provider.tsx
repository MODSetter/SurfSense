"use client";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { QueryClientAtomProvider } from "jotai-tanstack-query/react";
import { queryClient } from "./client";

export function ReactQueryClientProvider({ children }: { children: React.ReactNode }) {
	return (
		<QueryClientAtomProvider client={queryClient}>
			{children}
			<ReactQueryDevtools initialIsOpen={false} />
		</QueryClientAtomProvider>
	);
}
