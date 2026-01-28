"use client";

import { PostHogProvider as PHProvider } from "@posthog/react";
import posthog from "posthog-js";
import type { ReactNode } from "react";
import "../../instrumentation-client";
import { PostHogIdentify } from "./PostHogIdentify";

interface PostHogProviderProps {
	children: ReactNode;
}

export function PostHogProvider({ children }: PostHogProviderProps) {
	// posthog-js is initialized by importing instrumentation-client.ts above
	// We wrap the app with the PostHogProvider for hook access
	return (
		<PHProvider client={posthog}>
			<PostHogIdentify />
			{children}
		</PHProvider>
	);
}
