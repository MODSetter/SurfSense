"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";
import { AlertTriangle, Info } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { updateSearchSpaceMutationAtom } from "@/atoms/search-spaces/search-space-mutation.atoms";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { Spinner } from "../ui/spinner";

interface PromptConfigManagerProps {
	workspaceId: number;
}

export function PromptConfigManager({ workspaceId }: PromptConfigManagerProps) {
	const searchSpaceId = workspaceId;
	const { data: searchSpace, isLoading: loading } = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId.toString()),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const { mutateAsync: updateSearchSpace, isPending: isSaving } = useAtomValue(
		updateSearchSpaceMutationAtom
	);

	const [customInstructions, setCustomInstructions] = useState("");
	const hasSearchSpace = !!searchSpace;
	const searchSpaceInstructions = searchSpace?.qna_custom_instructions;

	// Initialize state from fetched search space
	useEffect(() => {
		if (hasSearchSpace) {
			setCustomInstructions(searchSpaceInstructions || "");
		}
	}, [hasSearchSpace, searchSpaceInstructions]);

	// Derive hasChanges during render
	const hasChanges =
		!!searchSpace && (searchSpace.qna_custom_instructions || "") !== customInstructions;

	const handleSave = async () => {
		try {
			await updateSearchSpace({
				id: searchSpaceId,
				data: { qna_custom_instructions: customInstructions.trim() || "" },
			});
			toast.success("System instructions saved successfully");
		} catch (error: unknown) {
			const message = error instanceof Error ? error.message : "Failed to save system instructions";
			console.error("Error saving system instructions:", error);
			toast.error(message);
		}
	};

	const onSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		handleSave();
	};

	if (loading) {
		return (
			<div className="space-y-4 md:space-y-6">
				<div className="space-y-3 md:space-y-4">
					<div className="space-y-2">
						<Skeleton className="h-5 md:h-6 w-36 md:w-48" />
						<Skeleton className="h-3 md:h-4 w-full max-w-md mt-2" />
					</div>
					<div className="space-y-3 md:space-y-4">
						<Skeleton className="h-16 md:h-20 w-full" />
						<Skeleton className="h-24 md:h-32 w-full" />
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="space-y-4 md:space-y-6">
			{/* Work in Progress Notice */}
			<Alert variant="warning">
				<AlertTriangle />
				<AlertTitle>Work in Progress</AlertTitle>
				<AlertDescription>
					This functionality is currently under development and not yet connected to the backend.
					Your instructions will be saved but won't affect AI behavior until the feature is fully
					implemented.
				</AlertDescription>
			</Alert>

			<Alert>
				<Info />
				<AlertDescription>
					System instructions apply to all AI interactions in this search space. They guide how the
					AI responds, its tone, focus areas, and behavior patterns.
				</AlertDescription>
			</Alert>

			{/* System Instructions Card */}
			<form onSubmit={onSubmit} className="space-y-4 md:space-y-6">
				<div className="space-y-3 md:space-y-4">
					<div className="space-y-1.5 md:space-y-2">
						<h3 className="text-base md:text-lg font-semibold tracking-tight">
							Custom System Instructions
						</h3>
						<p className="text-xs md:text-sm text-muted-foreground">
							Provide specific guidelines for how you want the AI to respond. These instructions
							will be applied to all answers in this search space.
						</p>
					</div>
					<div className="space-y-3 md:space-y-4">
						<div className="space-y-1.5 md:space-y-2">
							<Label
								htmlFor="custom-instructions-settings"
								className="text-sm md:text-base font-medium"
							>
								Your Instructions
							</Label>
							<Textarea
								id="custom-instructions-settings"
								placeholder="E.g., Always provide practical examples, be concise, focus on technical details, use simple language, respond in a specific format..."
								value={customInstructions}
								onChange={(e) => setCustomInstructions(e.target.value)}
								rows={10}
								className="resize-none font-mono text-xs md:text-sm"
							/>
							<div className="flex items-center justify-between">
								<p className="text-[10px] md:text-xs text-muted-foreground">
									{customInstructions.length} characters
								</p>
								{customInstructions.length > 0 && (
									<Button
										type="button"
										variant="ghost"
										size="sm"
										onClick={() => setCustomInstructions("")}
										className="h-auto py-0.5 md:py-1 px-1.5 md:px-2 text-[10px] md:text-xs"
									>
										Clear
									</Button>
								)}
							</div>
						</div>

						{customInstructions.trim().length === 0 && (
							<Alert>
								<Info />
								<AlertDescription>
									No system instructions are currently set. The AI will use default behavior.
								</AlertDescription>
							</Alert>
						)}
					</div>
				</div>

				{/* Action Buttons */}
				<div className="flex justify-end pt-3 md:pt-4">
					<Button
						type="submit"
						variant="outline"
						disabled={!hasChanges || isSaving}
						className="gap-2 bg-white text-black hover:bg-accent hover:text-accent-foreground dark:bg-white dark:text-black"
					>
						{isSaving ? <Spinner size="sm" /> : null}
						{isSaving ? "Saving" : "Save Instructions"}
					</Button>
				</div>
			</form>
		</div>
	);
}
