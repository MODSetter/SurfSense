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
import { useEffect, useMemo, useState } from "react";
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
	const [searchQuery, setSearchQuery] = useState("");

	useEffect(() => {
		window.electronAPI?.getQuickAskText().then((text) => {
			if (text) setClipboardText(text);
		});
	}, []);

	const navigateToChat = (prompt: string, mode: string) => {
		sessionStorage.setItem("quickAskMode", mode);
		sessionStorage.setItem("quickAskAutoSubmit", "true");
		const encoded = encodeURIComponent(prompt);
		window.location.href = `/dashboard?quickAskPrompt=${encoded}`;
	};

	const navigateWithInitialText = () => {
		if (!clipboardText) return;
		sessionStorage.setItem("quickAskMode", "explore");
		sessionStorage.setItem("quickAskAutoSubmit", "false");
		sessionStorage.setItem("quickAskInitialText", clipboardText);
		window.location.href = `/dashboard?quickAskPrompt=${encodeURIComponent(clipboardText)}`;
	};

	const handleAction = (actionId: string) => {
		const action = DEFAULT_ACTIONS.find((a) => a.id === actionId);
		if (!action || !clipboardText) return;
		const prompt = action.prompt.replace("{selection}", clipboardText);
		navigateToChat(prompt, action.mode);
	};

	const transformActions = DEFAULT_ACTIONS.filter((a) => a.group === "transform");
	const exploreActions = DEFAULT_ACTIONS.filter((a) => a.group === "explore");

	const filteredTransform = useMemo(
		() => transformActions.filter((a) => a.name.toLowerCase().includes(searchQuery.toLowerCase())),
		[searchQuery]
	);
	const filteredExplore = useMemo(
		() => exploreActions.filter((a) => a.name.toLowerCase().includes(searchQuery.toLowerCase())),
		[searchQuery]
	);

	if (!clipboardText) {
		return (
			<div className="flex h-screen items-center justify-center bg-background">
				<div className="text-sm text-muted-foreground">Loading...</div>
			</div>
		);
	}

	return (
		<div className="flex h-screen flex-col bg-background">
			<div className="border-b px-3 py-2">
				<div className="flex items-center gap-2 rounded-md border bg-muted/50 px-3 py-1.5">
					<Search className="size-3.5 text-muted-foreground" />
					<input
						type="text"
						placeholder="Search actions..."
						value={searchQuery}
						onChange={(e) => setSearchQuery(e.target.value)}
						className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
					/>
				</div>
			</div>

			<div className="flex-1 overflow-y-auto px-3 py-2">
				{filteredTransform.length > 0 && (
					<>
						<div className="mb-2 text-xs font-medium text-muted-foreground">Transform</div>
						<div className="mb-3 grid grid-cols-2 gap-1.5">
							{filteredTransform.map((action) => (
								<button
									key={action.id}
									type="button"
									onClick={() => handleAction(action.id)}
									className="flex items-center gap-2 rounded-md border px-3 py-2.5 text-sm transition-colors hover:bg-accent hover:border-accent-foreground/20 cursor-pointer"
								>
									<span className="text-muted-foreground">{ICONS[action.icon]}</span>
									{action.name}
								</button>
							))}
						</div>
					</>
				)}

				{filteredExplore.length > 0 && (
					<>
						<div className="mb-2 text-xs font-medium text-muted-foreground">Explore</div>
						<div className="mb-3 grid grid-cols-2 gap-1.5">
							{filteredExplore.map((action) => (
								<button
									key={action.id}
									type="button"
									onClick={() => handleAction(action.id)}
									className="flex items-center gap-2 rounded-md border px-3 py-2.5 text-sm transition-colors hover:bg-accent hover:border-accent-foreground/20 cursor-pointer"
								>
									<span className="text-muted-foreground">{ICONS[action.icon]}</span>
									{action.name}
								</button>
							))}
						</div>
					</>
				)}

				<div className="mb-2 text-xs font-medium text-muted-foreground">My Actions</div>
				<div className="mb-3 rounded-md border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
					Custom actions coming soon
				</div>
			</div>

			<div className="border-t px-3 py-2">
				<button
					type="button"
					onClick={navigateWithInitialText}
					className="flex w-full items-center justify-center gap-2 rounded-md bg-primary px-3 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 cursor-pointer"
				>
					<MessageSquare className="size-4" />
					Ask SurfSense...
				</button>
			</div>
		</div>
	);
}
