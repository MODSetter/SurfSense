"use client";

import { PostHogProvider as PHProvider } from "@posthog/react";
import posthog from "posthog-js";
import type { ReactNode } from "react";
import { PostHogIdentify } from "./PostHogIdentify";

interface PostHogProviderProps {
	children: ReactNode;
}

export function PostHogProvider({ children }: PostHogProviderProps) {
	// posthog-js is already initialized in instrumentation-client.ts
	// We just need to wrap the app with the PostHogProvider for hook access
	return (
		<PHProvider client={posthog}>
			<PostHogIdentify />
			{children}
		</PHProvider>
	);
}
