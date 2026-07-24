"use client";

import {
	AlarmClock,
	type LucideIcon,
	MessagesSquare,
	Radar,
	Settings2,
	WandSparkles,
	Workflow,
	X,
} from "lucide-react";
import { memo, useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { CHAT_EXAMPLE_CATEGORIES } from "@/lib/chat/example-prompts";

interface ChatExamplePromptsProps {
	/** Called with the chosen prompt text; the caller prefills the composer. */
	onSelect: (prompt: string) => void;
}

const CATEGORY_ICONS: Record<string, LucideIcon> = {
	monitor: Radar,
	listen: MessagesSquare,
	workflows: Workflow,
	automate: AlarmClock,
	tools: Settings2,
};

const ExamplePromptButton = memo(function ExamplePromptButton({
	prompt,
	onSelect,
}: {
	prompt: string;
	onSelect: (prompt: string) => void;
}) {
	const handleClick = useCallback(() => onSelect(prompt), [prompt, onSelect]);

	return (
		<Button
			type="button"
			variant="ghost"
			onClick={handleClick}
			className="h-auto w-full items-start justify-start whitespace-normal rounded-lg bg-transparent px-2.5 py-1.5 text-left font-normal text-muted-foreground shadow-none hover:bg-foreground/10 hover:text-foreground sm:rounded-xl sm:px-3 sm:py-2"
		>
			<span className="min-w-0 text-pretty text-xs sm:text-sm">{prompt}</span>
		</Button>
	);
});

export function ChatExamplePrompts({ onSelect }: ChatExamplePromptsProps) {
	const [activeCategoryId, setActiveCategoryId] = useState<string | null>(null);
	const activeCategory = CHAT_EXAMPLE_CATEGORIES.find(
		(category) => category.id === activeCategoryId
	);

	return (
		<div className="mt-2 w-full select-none sm:mt-3">
			{activeCategory ? null : (
				<div className="pb-1">
					<div className="mx-auto flex max-w-full flex-wrap items-center justify-center gap-1.5 px-0.5 sm:gap-2">
						{CHAT_EXAMPLE_CATEGORIES.map((category) => {
							const Icon = CATEGORY_ICONS[category.id] ?? WandSparkles;

							return (
								<Button
									key={category.id}
									type="button"
									variant="secondary"
									onClick={() => setActiveCategoryId(category.id)}
									className="h-8 rounded-lg bg-muted px-3 text-xs font-medium text-muted-foreground shadow-sm shadow-black/5 hover:bg-foreground/10 hover:text-foreground dark:shadow-black/10 sm:h-10 sm:rounded-xl sm:px-4 sm:text-sm"
								>
									<Icon aria-hidden="true" className="size-3.5 sm:size-4" />
									{category.label}
								</Button>
							);
						})}
					</div>
				</div>
			)}

			{activeCategory ? (
				<div className="overflow-hidden rounded-lg border border-input/20 bg-muted shadow-sm shadow-black/5 dark:shadow-black/10 sm:rounded-xl">
					<div className="flex items-center justify-between gap-2 px-3 py-2 sm:gap-3 sm:px-4 sm:py-3">
						<div className="flex min-w-0 items-center gap-2 text-xs font-medium text-muted-foreground sm:text-sm">
							<span className="truncate">{activeCategory.label}</span>
						</div>
						<Button
							type="button"
							variant="ghost"
							size="icon"
							onClick={() => setActiveCategoryId(null)}
							aria-label="Close example prompts"
							className="size-7 shrink-0 rounded-full text-muted-foreground hover:bg-foreground/10 hover:text-foreground sm:size-8"
						>
							<X aria-hidden="true" className="size-3.5 sm:size-4" />
						</Button>
					</div>
					<ScrollArea className="max-h-52 sm:max-h-64">
						<ul className="divide-y px-2 pb-2 sm:px-3 sm:pb-3">
							{activeCategory.prompts.map((prompt) => (
								<li key={prompt} className="py-0.5 sm:py-1">
									<ExamplePromptButton prompt={prompt} onSelect={onSelect} />
								</li>
							))}
						</ul>
					</ScrollArea>
				</div>
			) : null}
		</div>
	);
}
