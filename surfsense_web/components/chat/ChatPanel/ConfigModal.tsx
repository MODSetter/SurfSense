"use client";

import { Pencil } from "lucide-react";
import { useCallback, useContext } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { chatInterfaceContext } from "../ChatInterface";
import type { GeneratePodcastRequest } from "./actions";

interface ConfigModalProps {
	generatePodcast: (request: GeneratePodcastRequest) => Promise<void>;
}

export function ConfigModal(props: ConfigModalProps) {
	const context = useContext(chatInterfaceContext);

	if (!context) {
		throw new Error("chatInterfaceContext must be used within a ChatProvider");
	}
	const { chatDetails } = context;
	const { generatePodcast } = props;

	const handleGeneratePost = useCallback(async () => {
		if (!chatDetails) return;
		await generatePodcast({
			type: "CHAT",
			ids: [chatDetails.id],
			search_space_id: chatDetails.search_space_id,
			podcast_title: chatDetails.title,
		});
	}, [chatDetails]);
	return (
		<Popover>
			<PopoverTrigger>
				<button
					type="button"
					title="Edit the prompt"
					className="rounded-full p-2 bg-slate-400/30 hover:bg-slate-400/40"
				>
					<Pencil strokeWidth={1} className="h-4 w-4" />
				</button>
			</PopoverTrigger>
			<PopoverContent align="end" className="bg-sidebar w-96 ">
				<form className="flex flex-col gap-3 w-full">
					<label className="text-sm font-medium" htmlFor="prompt">
						What subjects should the AI cover in this podcast ?
					</label>

					<textarea
						name="prompt"
						id="prompt"
						defaultValue={chatDetails?.title}
						className="w-full rounded-md border border-slate-400/40 p-2"
					></textarea>

					<button
						type="button"
						onClick={handleGeneratePost}
						className="w-full rounded-md bg-foreground text-white dark:text-black p-2"
					>
						Generate Podcast
					</button>
				</form>
			</PopoverContent>
		</Popover>
	);
}
