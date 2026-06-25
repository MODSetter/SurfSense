"use client";

import { useAtomValue } from "jotai";
import { AlertTriangle, Copy, Library } from "lucide-react";
import { useCallback, useState } from "react";
import { copyPromptMutationAtom } from "@/atoms/prompts/prompts-mutation.atoms";
import { publicPromptsAtom } from "@/atoms/prompts/prompts-query.atoms";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

export function CommunityPromptsContent() {
	const { data: prompts, isLoading, isError } = useAtomValue(publicPromptsAtom);
	const { mutateAsync: copyPrompt } = useAtomValue(copyPromptMutationAtom);
	const [copyingIds, setCopyingIds] = useState<Set<number>>(new Set());
	const [expandedId, setExpandedId] = useState<number | null>(null);

	const handleCopy = useCallback(
		async (id: number) => {
			setCopyingIds((prev) => new Set(prev).add(id));
			try {
				await copyPrompt(id);
			} catch {
				// toast handled by mutation atom
			} finally {
				setCopyingIds((prev) => {
					const next = new Set(prev);
					next.delete(id);
					return next;
				});
			}
		},
		[copyPrompt]
	);

	const list = prompts ?? [];

	return (
		<div className="space-y-6 min-w-0">
			<p className="text-sm text-muted-foreground">
				Prompts shared by other users. Add any to your collection with one click.
			</p>

			{isLoading && (
				<div className="-m-1 space-y-2 p-1">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Card key={key} className="border-accent bg-accent/20">
							<CardContent className="p-4 flex flex-col gap-3 min-h-24">
								<Skeleton className="h-4 w-32 md:w-40 bg-accent" />
								<Skeleton className="h-3 w-full bg-accent" />
								<Skeleton className="h-3 w-24 md:w-28 bg-accent mt-auto" />
							</CardContent>
						</Card>
					))}
				</div>
			)}

			{isError && (
				<Alert variant="destructive">
					<AlertTriangle />
					<AlertTitle>Failed to load community prompts</AlertTitle>
					<AlertDescription>Please try refreshing the page.</AlertDescription>
				</Alert>
			)}

			{!isLoading && !isError && list.length === 0 && (
				<div className="rounded-lg border border-dashed border-border/60 p-8 text-center">
					<Library className="mx-auto size-8 text-muted-foreground" />
					<p className="mt-2 text-sm text-muted-foreground">No community prompts yet</p>
					<p className="text-xs text-muted-foreground/60">
						Share your own prompts from the My Prompts tab
					</p>
				</div>
			)}

			{!isLoading && !isError && list.length > 0 && (
				<div className="-m-1 space-y-2 p-1">
					{list.map((prompt) => (
						<Card
							key={prompt.id}
							className="group relative overflow-hidden transition-all duration-200 border-accent bg-accent/20 hover:shadow-md h-full"
						>
							<CardContent className="p-4 flex items-start gap-3 h-full">
								<div className="flex-1 min-w-0">
									<div className="flex items-center gap-2">
										<span className="text-sm font-medium">{prompt.name}</span>
										<span className="rounded-md border-0 bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
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
										<Button
											type="button"
											variant="link"
											onClick={() => setExpandedId(expandedId === prompt.id ? null : prompt.id)}
											className="mt-1 h-auto cursor-pointer px-0 py-0 text-[11px] text-primary"
										>
											{expandedId === prompt.id ? "See less" : "See more"}
										</Button>
									)}
								</div>
								<Button
									variant="ghost"
									size="sm"
									className="h-7 shrink-0 gap-1.5 rounded-lg px-2 text-muted-foreground hover:text-accent-foreground"
									disabled={copyingIds.has(prompt.id)}
									onClick={() => handleCopy(prompt.id)}
								>
									{copyingIds.has(prompt.id) ? (
										<Spinner className="size-3" />
									) : (
										<Copy className="size-3" />
									)}
									Add to mine
								</Button>
							</CardContent>
						</Card>
					))}
				</div>
			)}
		</div>
	);
}
