"use client";

import dynamic from "next/dynamic";

const FreeChatApp = dynamic(() => import("./free-chat-app").then((mod) => mod.FreeChatApp), {
	ssr: false,
	loading: () => <div className="h-full" />,
});

/** Client-only chat chrome. Must not SSR — the shell touches `document`. */
export function FreeChatClient({ modelSlug }: { modelSlug: string }) {
	return <FreeChatApp modelSlug={modelSlug} />;
}
