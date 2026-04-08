import { PostHog } from "posthog-node";

let posthogInstance: PostHog | null = null;

export default function PostHogClient() {
	if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) {
		throw new Error("NEXT_PUBLIC_POSTHOG_KEY is not set");
	}

	if (!posthogInstance) {
		posthogInstance = new PostHog(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
			host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
			flushAt: 1,
			flushInterval: 0,
		});
	}

	return posthogInstance;
}
