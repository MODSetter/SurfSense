"use client";

import { CornerDownLeft, Lightbulb } from "lucide-react";
import { memo, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CHAT_EXAMPLE_CATEGORIES } from "@/lib/chat/example-prompts";

interface ChatExamplePromptsProps {
	/** Called with the chosen prompt text; the caller prefills the composer. */
	onSelect: (prompt: string) => void;
}

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
			className="h-auto w-full items-start justify-start gap-2.5 whitespace-normal rounded-md border bg-background px-3 py-2 text-left font-normal text-muted-foreground hover:bg-accent hover:text-accent-foreground"
		>
			<CornerDownLeft
				aria-hidden="true"
				className="mt-0.5 size-3.5 shrink-0 text-muted-foreground/70"
			/>
			<span className="min-w-0 text-pretty text-sm">{prompt}</span>
		</Button>
	);
});

export function ChatExamplePrompts({ onSelect }: ChatExamplePromptsProps) {
	return (
		<div className="mt-3 w-full select-none rounded-xl border border-dashed bg-muted/30 p-3 sm:p-4">
			<div className="mb-2 flex items-center gap-2 px-1">
				<Lightbulb aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
				<p className="text-sm font-medium text-foreground">
					Not sure where to start? Try one of these
				</p>
			</div>
			<Tabs defaultValue={CHAT_EXAMPLE_CATEGORIES[0].id} className="w-full">
				<div className="overflow-x-auto pb-1">
					<TabsList className="h-9 w-max">
						{CHAT_EXAMPLE_CATEGORIES.map((category) => (
							<TabsTrigger key={category.id} value={category.id} className="text-xs">
								{category.label}
							</TabsTrigger>
						))}
					</TabsList>
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
