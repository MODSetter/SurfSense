import { PostHog } from "posthog-node";

export default function PostHogClient() {
	if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) {
		throw new Error("NEXT_PUBLIC_POSTHOG_KEY is not set");
	}

	const posthogClient = new PostHog(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
		host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
		// Because server-side functions in Next.js can be short-lived,
		// we set flushAt to 1 and flushInterval to 0 to ensure events are sent immediately
		flushAt: 1,
		flushInterval: 0,
	});

	return posthogClient;
}
