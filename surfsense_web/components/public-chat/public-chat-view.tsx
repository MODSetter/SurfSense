"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { Loader2 } from "lucide-react";
import { DisplayImageToolUI } from "@/components/tool-ui/display-image";
import { GeneratePodcastToolUI } from "@/components/tool-ui/generate-podcast";
import { LinkPreviewToolUI } from "@/components/tool-ui/link-preview";
import { ScrapeWebpageToolUI } from "@/components/tool-ui/scrape-webpage";
import { usePublicChat } from "@/hooks/use-public-chat";
import { usePublicChatRuntime } from "@/hooks/use-public-chat-runtime";
import { PublicChatFooter } from "./public-chat-footer";
import { PublicChatHeader } from "./public-chat-header";
import { PublicThread } from "./public-thread";

interface PublicChatViewProps {
	shareToken: string;
}

export function PublicChatView({ shareToken }: PublicChatViewProps) {
	const { data, isLoading, error } = usePublicChat(shareToken);
	const runtime = usePublicChatRuntime({ data });

	if (isLoading) {
		return (
			<div className="flex h-screen items-center justify-center">
				<Loader2 className="size-8 animate-spin text-muted-foreground" />
			</div>
		);
	}

	if (error || !data) {
		return (
			<div className="flex h-screen flex-col items-center justify-center gap-4 px-4 text-center">
				<h1 className="text-2xl font-semibold">Chat not found</h1>
				<p className="text-muted-foreground">
					This chat may have been removed or is no longer public.
				</p>
			</div>
		);
	}

	return (
		<AssistantRuntimeProvider runtime={runtime}>
			{/* Tool UIs for rendering tool results */}
			<GeneratePodcastToolUI />
			<LinkPreviewToolUI />
			<DisplayImageToolUI />
			<ScrapeWebpageToolUI />

			<div className="flex h-screen flex-col bg-background">
				<PublicThread
					header={<PublicChatHeader title={data.thread.title} createdAt={data.thread.created_at} />}
					footer={<PublicChatFooter shareToken={shareToken} />}
				/>
			</div>
		</AssistantRuntimeProvider>
	);
}
