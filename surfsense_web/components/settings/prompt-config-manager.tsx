"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { searchSpacesApiService } from "@/lib/apis/search-spaces-api.service";
import { authenticatedFetch } from "@/lib/auth-utils";
import { cacheKeys } from "@/lib/query-client/cache-keys";

interface PromptConfigManagerProps {
	searchSpaceId: number;
}

export function PromptConfigManager({ searchSpaceId }: PromptConfigManagerProps) {
	const {
		data: searchSpace,
		isLoading: loading,
		refetch: fetchSearchSpace,
	} = useQuery({
		queryKey: cacheKeys.searchSpaces.detail(searchSpaceId.toString()),
		queryFn: () => searchSpacesApiService.getSearchSpace({ id: searchSpaceId }),
		enabled: !!searchSpaceId,
	});

	const [customInstructions, setCustomInstructions] = useState("");
	const [saving, setSaving] = useState(false);
	const [hasChanges, setHasChanges] = useState(false);

	// Initialize state from fetched search space
	useEffect(() => {
		if (searchSpace) {
			setCustomInstructions(searchSpace.qna_custom_instructions || "");
			setHasChanges(false);
		}
	}, [searchSpace]);

	// Track changes
	useEffect(() => {
		if (searchSpace) {
			const currentCustom = searchSpace.qna_custom_instructions || "";
			const changed = currentCustom !== customInstructions;
			setHasChanges(changed);
		}
	}, [searchSpace, customInstructions]);

	const handleSave = async () => {
		try {
			setSaving(true);

			const payload = {
				qna_custom_instructions: customInstructions.trim() || "",
			};

			const response = await authenticatedFetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}`,
				{
					method: "PUT",
					headers: { "Content-Type": "application/json" },
					body: JSON.stringify(payload),
				}
			);

			if (!response.ok) {
				const errorData = await response.json().catch(() => ({}));
				throw new Error(errorData.detail || "Failed to save system instructions");
			}

			toast.success("System instructions saved successfully");
			setHasChanges(false);
			await fetchSearchSpace();
		} catch (error: any) {
			console.error("Error saving system instructions:", error);
			toast.error(error.message || "Failed to save system instructions");
		} finally {
			setSaving(false);
		}
	};

	const handleReset = () => {
		if (searchSpace) {
			setCustomInstructions(searchSpace.qna_custom_instructions || "");
			setHasChanges(false);
		}
	};

	if (loading) {
		return (
			<div className="space-y-4 md:space-y-6">
				<Card>
					<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
						<Skeleton className="h-5 md:h-6 w-36 md:w-48" />
						<Skeleton className="h-3 md:h-4 w-full max-w-md mt-2" />
					</CardHeader>
					<CardContent className="space-y-3 md:space-y-4 px-3 md:px-6 pb-3 md:pb-6">
						<Skeleton className="h-16 md:h-20 w-full" />
						<Skeleton className="h-24 md:h-32 w-full" />
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<div className="space-y-4 md:space-y-6">
			{/* Work in Progress Notice */}
			<Alert
				variant="default"
				className="bg-amber-50 dark:bg-amber-950/30 border-amber-300 dark:border-amber-700 py-3 md:py-4"
			>
				<AlertTriangle className="h-3 w-3 md:h-4 md:w-4 text-amber-600 dark:text-amber-500 shrink-0" />
				<AlertDescription className="text-amber-800 dark:text-amber-300 text-xs md:text-sm">
					<span className="font-semibold">Work in Progress:</span> This functionality is currently
					under development and not yet connected to the backend. Your instructions will be saved
					but won't affect AI behavior until the feature is fully implemented.
				</AlertDescription>
			</Alert>

			<Alert className="py-3 md:py-4">
				<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
				<AlertDescription className="text-xs md:text-sm">
					System instructions apply to all AI interactions in this search space. They guide how the
					AI responds, its tone, focus areas, and behavior patterns.
				</AlertDescription>
			</Alert>

			{/* System Instructions Card */}
			<Card>
				<CardHeader className="px-3 md:px-6 pt-3 md:pt-6 pb-2 md:pb-3">
					<CardTitle className="text-base md:text-lg">Custom System Instructions</CardTitle>
					<CardDescription className="text-xs md:text-sm">
						Provide specific guidelines for how you want the AI to respond. These instructions will
						be applied to all answers in this search space.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3 md:space-y-4 px-3 md:px-6 pb-3 md:pb-6">
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
						<Alert className="py-2 md:py-3">
							<Info className="h-3 w-3 md:h-4 md:w-4 shrink-0" />
							<AlertDescription className="text-xs md:text-sm">
								No system instructions are currently set. The AI will use default behavior.
							</AlertDescription>
						</Alert>
					)}
				</CardContent>
			</Card>

			{/* Action Buttons */}
			<div className="flex items-center justify-between pt-3 md:pt-4 gap-2">
				<Button
					variant="outline"
					onClick={handleReset}
					disabled={!hasChanges || saving}
					className="flex items-center gap-2 text-xs md:text-sm h-9 md:h-10"
				>
					<RotateCcw className="h-3.5 w-3.5 md:h-4 md:w-4" />
					Reset Changes
				</Button>
				<Button
					onClick={handleSave}
					disabled={!hasChanges || saving}
					className="flex items-center gap-2 text-xs md:text-sm h-9 md:h-10"
				>
					<Save className="h-3.5 w-3.5 md:h-4 md:w-4" />
					{saving ? "Saving" : "Save Instructions"}
				</Button>
			</div>

			{hasChanges && (
				<Alert
					variant="default"
					className="bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800 py-3 md:py-4"
				>
					<Info className="h-3 w-3 md:h-4 md:w-4 text-blue-600 dark:text-blue-500 shrink-0" />
					<AlertDescription className="text-blue-800 dark:text-blue-300 text-xs md:text-sm">
						You have unsaved changes. Click "Save Instructions" to apply them.
					</AlertDescription>
				</Alert>
			)}
		</div>
	);
}
