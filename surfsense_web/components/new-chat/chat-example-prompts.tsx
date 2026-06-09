"use client";

import {
	FilePlus2,
	Search,
	Settings2,
	type LucideIcon,
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
	search: Search,
	create: FilePlus2,
	automate: Workflow,
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
				{CHAT_EXAMPLE_CATEGORIES.map((category) => (
					<TabsContent
						key={category.id}
						value={category.id}
						className="mt-3 focus-visible:outline-none"
					>
						<ScrollArea className="h-[clamp(7.5rem,26vh,12rem)]">
							<ul className="flex flex-col gap-2 pr-3">
								{category.prompts.map((prompt) => (
									<li key={prompt}>
										<ExamplePromptButton prompt={prompt} onSelect={onSelect} />
									</li>
								))}
							</ul>
						</ScrollArea>
					</TabsContent>
				))}
			</Tabs>
		</div>
	);
}