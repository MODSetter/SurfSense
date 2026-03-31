"use client";

import { useAtomValue } from "jotai";
import { Copy, Globe, Sparkles } from "lucide-react";
import { useCallback, useState } from "react";
import { copyPromptMutationAtom } from "@/atoms/prompts/prompts-mutation.atoms";
import { publicPromptsAtom } from "@/atoms/prompts/prompts-query.atoms";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export function CommunityPromptsContent() {
	const { data: prompts, isLoading } = useAtomValue(publicPromptsAtom);
	const { mutateAsync: copyPrompt, isPending: isCopying } = useAtomValue(copyPromptMutationAtom);
	const [copyingId, setCopyingId] = useState<number | null>(null);
	const [expandedId, setExpandedId] = useState<number | null>(null);

	const handleCopy = useCallback(
		async (id: number) => {
			setCopyingId(id);
			try {
				await copyPrompt(id);
			} catch {
				// toast handled by mutation atom
			} finally {
				setCopyingId(null);
			}
		},
		[copyPrompt]
	);

	const list = prompts ?? [];

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

			{list.length === 0 && (
				<div className="rounded-lg border border-dashed border-border/60 p-8 text-center">
					<Globe className="mx-auto size-8 text-muted-foreground/40" />
					<p className="mt-2 text-sm text-muted-foreground">No community prompts yet</p>
					<p className="text-xs text-muted-foreground/60">
						Share your own prompts from the My Prompts tab
					</p>
				</div>
			)}

			{list.length > 0 && (
				<div className="space-y-2">
					{list.map((prompt) => (
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
									{prompt.author_name && (
										<span className="text-[11px] text-muted-foreground/60">
											by {prompt.author_name}
										</span>
									)}
								</div>
								<p
									className={`mt-1 text-xs text-muted-foreground ${expandedId === prompt.id ? "whitespace-pre-wrap" : "line-clamp-2"}`}
								>
									{prompt.prompt}
								</p>
								{prompt.prompt.length > 100 && (
									<button
										type="button"
										onClick={() => setExpandedId(expandedId === prompt.id ? null : prompt.id)}
										className="mt-1 text-[11px] text-primary hover:underline cursor-pointer"
									>
										{expandedId === prompt.id ? "See less" : "See more"}
									</button>
								)}
							</div>
							<Button
								variant="outline"
								size="sm"
								className="shrink-0 gap-1.5"
								disabled={copyingId === prompt.id && isCopying}
								onClick={() => handleCopy(prompt.id)}
							>
								{copyingId === prompt.id && isCopying ? (
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
