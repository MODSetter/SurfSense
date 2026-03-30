"use client";

import { Copy, Globe, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import type { PublicPromptRead } from "@/contracts/types/prompts.types";
import { promptsApiService } from "@/lib/apis/prompts-api.service";

export function CommunityPromptsContent() {
	const [prompts, setPrompts] = useState<PublicPromptRead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [copyingId, setCopyingId] = useState<number | null>(null);

	useEffect(() => {
		promptsApiService
			.listPublic()
			.then(setPrompts)
			.catch(() => toast.error("Failed to load community prompts"))
			.finally(() => setIsLoading(false));
	}, []);

	const handleCopy = useCallback(async (id: number) => {
		setCopyingId(id);
		try {
			await promptsApiService.copy(id);
			toast.success("Prompt added to your collection");
		} catch {
			toast.error("Failed to copy prompt");
		} finally {
			setCopyingId(null);
		}
	}, []);

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner className="size-6" />
			</div>
		);
	}

	return (
		<div className="space-y-6 min-w-0 overflow-hidden">
			<p className="text-sm text-muted-foreground">
				Prompts shared by other users. Add any to your collection with one click.
			</p>

			{prompts.length === 0 && (
				<div className="rounded-lg border border-dashed border-border/60 p-8 text-center">
					<Globe className="mx-auto size-8 text-muted-foreground/40" />
					<p className="mt-2 text-sm text-muted-foreground">No community prompts yet</p>
					<p className="text-xs text-muted-foreground/60">
						Share your own prompts from the My Prompts tab
					</p>
				</div>
			)}

			{prompts.length > 0 && (
				<div className="space-y-2">
					{prompts.map((prompt) => (
						<div
							key={prompt.id}
							className="group flex items-start gap-3 rounded-lg border border-border/60 bg-card p-4"
						>
							<div className="mt-0.5 shrink-0 text-muted-foreground">
								<Sparkles className="size-4" />
							</div>
							<div className="flex-1 min-w-0">
								<div className="flex items-center gap-2">
									<span className="text-sm font-medium">{prompt.name}</span>
									<span className="rounded-full border px-2 py-0.5 text-[10px] text-muted-foreground">
										{prompt.mode}
									</span>
								</div>
								<p className="mt-1 text-xs text-muted-foreground line-clamp-2">{prompt.prompt}</p>
								{prompt.author_name && (
									<p className="mt-1.5 text-[11px] text-muted-foreground/60">
										by {prompt.author_name}
									</p>
								)}
							</div>
							<Button
								variant="outline"
								size="sm"
								className="shrink-0 gap-1.5"
								disabled={copyingId === prompt.id}
								onClick={() => handleCopy(prompt.id)}
							>
								{copyingId === prompt.id ? (
									<Spinner className="size-3" />
								) : (
									<Copy className="size-3" />
								)}
								Add to mine
							</Button>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
