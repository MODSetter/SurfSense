"use client";

import {
	BookOpen,
	Check,
	Globe,
	Languages,
	List,
	MessageSquare,
	Minimize2,
	PenLine,
	Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
	Command,
	CommandEmpty,
	CommandGroup,
	CommandInput,
	CommandItem,
	CommandList,
	CommandSeparator,
} from "@/components/ui/command";
import { DEFAULT_ACTIONS } from "./actions";

const ICONS: Record<string, React.ReactNode> = {
	check: <Check className="size-4" />,
	minimize: <Minimize2 className="size-4" />,
	languages: <Languages className="size-4" />,
	"pen-line": <PenLine className="size-4" />,
	"book-open": <BookOpen className="size-4" />,
	list: <List className="size-4" />,
	search: <Search className="size-4" />,
	globe: <Globe className="size-4" />,
};

export default function QuickAskPage() {
	const [clipboardText, setClipboardText] = useState("");

	useEffect(() => {
		window.electronAPI?.getQuickAskText().then((text) => {
			if (text) setClipboardText(text);
		});
	}, []);

	const handleAction = (actionId: string) => {
		const action = DEFAULT_ACTIONS.find((a) => a.id === actionId);
		if (!action || !clipboardText) return;

		const prompt = action.prompt.replace("{selection}", clipboardText);
		const encoded = encodeURIComponent(prompt);
		const mode = action.mode;

		window.location.href = `/dashboard?quickAskPrompt=${encoded}&quickAskMode=${mode}`;
	};

	const handleAskAnything = () => {
		if (!clipboardText) return;
		const encoded = encodeURIComponent(clipboardText);
		window.location.href = `/dashboard?quickAskPrompt=${encoded}&quickAskMode=explore`;
	};

	const transformActions = DEFAULT_ACTIONS.filter((a) => a.group === "transform");
	const exploreActions = DEFAULT_ACTIONS.filter((a) => a.group === "explore");
	const knowledgeActions = DEFAULT_ACTIONS.filter((a) => a.group === "knowledge");

	return (
		<div className="flex h-screen items-start justify-center bg-background pt-2">
			<Command className="max-w-md border shadow-lg rounded-lg">
				<CommandInput placeholder="Search actions..." />
				<CommandList>
					<CommandEmpty>No actions found.</CommandEmpty>

					<CommandGroup heading="Transform">
						{transformActions.map((action) => (
							<CommandItem key={action.id} onSelect={() => handleAction(action.id)}>
								{ICONS[action.icon]}
								<span>{action.name}</span>
							</CommandItem>
						))}
					</CommandGroup>

					<CommandSeparator />

					<CommandGroup heading="Explore">
						{exploreActions.map((action) => (
							<CommandItem key={action.id} onSelect={() => handleAction(action.id)}>
								{ICONS[action.icon]}
								<span>{action.name}</span>
							</CommandItem>
						))}
					</CommandGroup>

					<CommandSeparator />

					<CommandGroup heading="Knowledge">
						{knowledgeActions.map((action) => (
							<CommandItem key={action.id} onSelect={() => handleAction(action.id)}>
								{ICONS[action.icon]}
								<span>{action.name}</span>
							</CommandItem>
						))}
					</CommandGroup>

					<CommandSeparator />

					<CommandGroup>
						<CommandItem onSelect={handleAskAnything}>
							<MessageSquare className="size-4" />
							<span>Ask anything...</span>
						</CommandItem>
					</CommandGroup>
				</CommandList>
			</Command>
		</div>
	);
}
