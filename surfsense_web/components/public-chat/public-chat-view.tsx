"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { Loader2 } from "lucide-react";
import { Navbar } from "@/components/homepage/navbar";
import { DisplayImageToolUI } from "@/components/tool-ui/display-image";
import { GeneratePodcastToolUI } from "@/components/tool-ui/generate-podcast";
import { LinkPreviewToolUI } from "@/components/tool-ui/link-preview";
import { ScrapeWebpageToolUI } from "@/components/tool-ui/scrape-webpage";
import { usePublicChat } from "@/hooks/use-public-chat";
import { usePublicChatRuntime } from "@/hooks/use-public-chat-runtime";
import { PublicChatFooter } from "./public-chat-footer";
import { PublicThread } from "./public-thread";

interface PublicChatViewProps {
	shareToken: string;
}

export function PublicChatView({ shareToken }: PublicChatViewProps) {
	const { data, isLoading, error } = usePublicChat(shareToken);
	const runtime = usePublicChatRuntime({ data });

	if (isLoading) {
		return (
			<main className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white overflow-x-hidden">
				<Navbar />
				<div className="flex h-screen items-center justify-center">
					<Loader2 className="size-8 animate-spin text-muted-foreground" />
				</div>
			</main>
		);
	}

	if (error || !data) {
		return (
			<main className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white overflow-x-hidden">
				<Navbar />
				<div className="flex h-screen flex-col items-center justify-center gap-4 px-4 text-center">
					<h1 className="text-2xl font-semibold">Chat not found</h1>
					<p className="text-muted-foreground">
						This chat may have been removed or is no longer public.
					</p>
				</div>
			</main>
		);
	}

	return (
		<main className="min-h-screen bg-linear-to-b from-gray-50 to-gray-100 text-gray-900 dark:from-black dark:to-gray-900 dark:text-white overflow-x-hidden">
			<Navbar />
			<AssistantRuntimeProvider runtime={runtime}>
				{/* Tool UIs for rendering tool results */}
				<GeneratePodcastToolUI />
				<LinkPreviewToolUI />
				<DisplayImageToolUI />
				<ScrapeWebpageToolUI />

				<div className="flex h-screen flex-col pt-16">
					<PublicThread footer={<PublicChatFooter shareToken={shareToken} />} />
				</div>
			</AssistantRuntimeProvider>
		</main>
	);
}
