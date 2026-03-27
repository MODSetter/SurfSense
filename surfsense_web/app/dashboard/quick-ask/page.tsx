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

	const navigateToChat = (prompt: string, mode: string) => {
		sessionStorage.setItem("quickAskMode", mode);
		const encoded = encodeURIComponent(prompt);
		window.location.href = `/dashboard?quickAskPrompt=${encoded}`;
	};

	const handleAction = (actionId: string) => {
		const action = DEFAULT_ACTIONS.find((a) => a.id === actionId);
		if (!action) return;
		const prompt = action.prompt.replace("{selection}", clipboardText);
		navigateToChat(prompt, action.mode);
	};

	const transformActions = DEFAULT_ACTIONS.filter((a) => a.group === "transform");
	const exploreActions = DEFAULT_ACTIONS.filter((a) => a.group === "explore");
	const knowledgeActions = DEFAULT_ACTIONS.filter((a) => a.group === "knowledge");

	return (
		<div className="flex h-screen flex-col bg-background">
			<div className="flex-1 overflow-y-auto">
				{!clipboardText && (
					<div className="p-4 text-center text-sm text-muted-foreground">Loading...</div>
				)}
				{clipboardText && (
					<div className="py-1">
						<div className="px-3 py-1.5 text-xs font-medium text-muted-foreground">Transform</div>
						{transformActions.map((action) => (
							<button
								key={action.id}
								type="button"
								onClick={() => handleAction(action.id)}
								className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent rounded-sm cursor-pointer"
							>
								{ICONS[action.icon]}
								{action.name}
							</button>
						))}

						<div className="my-1 h-px bg-border" />

						<div className="px-3 py-1.5 text-xs font-medium text-muted-foreground">Explore</div>
						{exploreActions.map((action) => (
							<button
								key={action.id}
								type="button"
								onClick={() => handleAction(action.id)}
								className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent rounded-sm cursor-pointer"
							>
								{ICONS[action.icon]}
								{action.name}
							</button>
						))}

						<div className="my-1 h-px bg-border" />

						<div className="px-3 py-1.5 text-xs font-medium text-muted-foreground">Knowledge</div>
						{knowledgeActions.map((action) => (
							<button
								key={action.id}
								type="button"
								onClick={() => handleAction(action.id)}
								className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent rounded-sm cursor-pointer"
							>
								{ICONS[action.icon]}
								{action.name}
							</button>
						))}

						<div className="my-1 h-px bg-border" />

						<button
							type="button"
							onClick={() => navigateToChat(clipboardText, "explore")}
							className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent rounded-sm cursor-pointer"
						>
							<MessageSquare className="size-4" />
							Ask anything...
						</button>
					</div>
				)}
			</div>
		</div>
	);
}
