"use client";

import { PostHogProvider as PHProvider } from "@posthog/react";
import posthog from "posthog-js";
import type { ReactNode } from "react";
import "../../instrumentation-client";
import { PostHogIdentify } from "./PostHogIdentify";
import { PostHogReferral } from "./PostHogReferral";

interface PostHogProviderProps {
	children: ReactNode;
}

export function PostHogProvider({ children }: PostHogProviderProps) {
	return (
		<PHProvider client={posthog}>
			<PostHogIdentify />
			<PostHogReferral />
			{children}
		</PHProvider>
	);
}
