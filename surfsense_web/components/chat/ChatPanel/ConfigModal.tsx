"use client";

import { useAtomValue } from "jotai";
import { Pencil } from "lucide-react";
import { useCallback, useContext, useState } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { activeChatAtom } from "@/stores/chats/active-chat.atom";
import type { GeneratePodcastRequest } from "./ChatPanelContainer";

interface ConfigModalProps {
	generatePodcast: (request: GeneratePodcastRequest) => Promise<void>;
}

export function ConfigModal(props: ConfigModalProps) {
	const { data: activeChatState } = useAtomValue(activeChatAtom);

	const chatDetails = activeChatState?.chatDetails;
	const podcast = activeChatState?.podcast;

	const { generatePodcast } = props;

	const [userPromt, setUserPrompt] = useState("");

	const handleGeneratePost = useCallback(async () => {
		if (!chatDetails) return;
		await generatePodcast({
			type: "CHAT",
			ids: [chatDetails.id],
			search_space_id: chatDetails.search_space_id,
			podcast_title: podcast?.title || chatDetails.title,
			user_prompt: userPromt,
		});
	}, [chatDetails, userPromt]);

	return (
		<Popover>
			<PopoverTrigger
				title="Edit the prompt"
				className="rounded-full p-2 bg-slate-400/30 hover:bg-slate-400/40"
				onClick={(e) => e.stopPropagation()}
			>
				<Pencil strokeWidth={1} className="h-4 w-4" />
			</PopoverTrigger>
			<PopoverContent onClick={(e) => e.stopPropagation()} align="end" className="bg-sidebar w-96 ">
				<form className="flex flex-col gap-3 w-full">
					<label className="text-sm font-medium" htmlFor="prompt">
						Special user instructions
					</label>
					<p className="text-xs text-slate-500 dark:text-slate-400">
						Leave empty to use the default prompt
					</p>
					<div className="text-xs text-slate-500 dark:text-slate-400 space-y-1">
						<p>Examples:</p>
						<ul className="list-disc list-inside space-y-0.5">
							<li>Make hosts speak in London street language</li>
							<li>Use real-world analogies and metaphors</li>
							<li>Add dramatic pauses like a late-night radio show</li>
							<li>Include 90s pop culture references</li>
						</ul>
					</div>

					<textarea
						name="prompt"
						id="prompt"
						defaultValue={userPromt}
						className="w-full rounded-md border border-slate-400/40 p-2"
						onChange={(e) => {
							e.stopPropagation();
							setUserPrompt(e.target.value);
						}}
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
