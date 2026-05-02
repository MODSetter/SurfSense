"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { StepSeparatorDataUI } from "@/components/assistant-ui/step-separator";
import { ThinkingStepsDataUI } from "@/components/assistant-ui/thinking-steps";
import { Navbar } from "@/components/homepage/navbar";
import { ReportPanel } from "@/components/report-panel/report-panel";
import { Spinner } from "@/components/ui/spinner";
import { usePublicChat } from "@/hooks/use-public-chat";
import { usePublicChatRuntime } from "@/hooks/use-public-chat-runtime";
import { PublicChatFooter } from "./public-chat-footer";
import { PublicChatNotFound } from "./public-chat-not-found";
import { PublicThread } from "./public-thread";

interface PublicChatViewProps {
	shareToken: string;
}

export function PublicChatView({ shareToken }: PublicChatViewProps) {
	const { data, isLoading, error } = usePublicChat(shareToken);
	const runtime = usePublicChatRuntime({ data });

	const navbarScrolledBg = "bg-main-panel/80 backdrop-blur-md border border-border/30 shadow-lg";

	if (isLoading) {
		return (
			<main className="min-h-screen bg-main-panel text-foreground overflow-x-hidden">
				<Navbar scrolledBgClassName={navbarScrolledBg} />
				<div className="flex h-screen items-center justify-center">
					<Spinner size="lg" className="text-muted-foreground" />
				</div>
			</main>
		);
	}

	if (error || !data) {
		return <PublicChatNotFound />;
	}

	return (
		<main className="min-h-screen bg-main-panel text-foreground overflow-x-hidden">
			<Navbar scrolledBgClassName={navbarScrolledBg} />
			<AssistantRuntimeProvider runtime={runtime}>
				<ThinkingStepsDataUI />
				<StepSeparatorDataUI />
				<div className="flex h-screen pt-16 overflow-hidden">
					<div className="flex-1 flex flex-col min-w-0 overflow-hidden">
						<PublicThread footer={<PublicChatFooter shareToken={shareToken} />} />
					</div>
					<ReportPanel />
				</div>
			</AssistantRuntimeProvider>
		</main>
	);
}
