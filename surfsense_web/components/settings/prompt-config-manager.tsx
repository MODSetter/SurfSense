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
			<div className="space-y-6">
				<Card>
					<CardHeader>
						<Skeleton className="h-6 w-48" />
						<Skeleton className="h-4 w-full max-w-md" />
					</CardHeader>
					<CardContent className="space-y-4">
						<Skeleton className="h-20 w-full" />
						<Skeleton className="h-32 w-full" />
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<div className="space-y-6">
			{/* Work in Progress Notice */}
			<Alert
				variant="default"
				className="bg-amber-50 dark:bg-amber-950/30 border-amber-300 dark:border-amber-700"
			>
				<AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-500" />
				<AlertDescription className="text-amber-800 dark:text-amber-300">
					<span className="font-semibold">Work in Progress:</span> This functionality is currently
					under development and not yet connected to the backend. Your instructions will be saved
					but won't affect AI behavior until the feature is fully implemented.
				</AlertDescription>
			</Alert>

			<Alert>
				<Info className="h-4 w-4" />
				<AlertDescription>
					System instructions apply to all AI interactions in this search space. They guide how the
					AI responds, its tone, focus areas, and behavior patterns.
				</AlertDescription>
			</Alert>

			{/* System Instructions Card */}
			<Card>
				<CardHeader>
					<CardTitle>Custom System Instructions</CardTitle>
					<CardDescription>
						Provide specific guidelines for how you want the AI to respond. These instructions will
						be applied to all answers in this search space.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="custom-instructions-settings" className="text-base font-medium">
							Your Instructions
						</Label>
						<Textarea
							id="custom-instructions-settings"
							placeholder="E.g., Always provide practical examples, be concise, focus on technical details, use simple language, respond in a specific format..."
							value={customInstructions}
							onChange={(e) => setCustomInstructions(e.target.value)}
							rows={12}
							className="resize-none font-mono text-sm"
						/>
						<div className="flex items-center justify-between">
							<p className="text-xs text-muted-foreground">
								{customInstructions.length} characters
							</p>
							{customInstructions.length > 0 && (
								<Button
									variant="ghost"
									size="sm"
									onClick={() => setCustomInstructions("")}
									className="h-auto py-1 px-2 text-xs"
								>
									Clear
								</Button>
							)}
						</div>
					</div>

					{customInstructions.trim().length === 0 && (
						<Alert>
							<Info className="h-4 w-4" />
							<AlertDescription>
								No system instructions are currently set. The AI will use default behavior.
							</AlertDescription>
						</Alert>
					)}
				</CardContent>
			</Card>

			{/* Action Buttons */}
			<div className="flex items-center justify-between pt-4">
				<Button
					variant="outline"
					onClick={handleReset}
					disabled={!hasChanges || saving}
					className="flex items-center gap-2"
				>
					<RotateCcw className="h-4 w-4" />
					Reset Changes
				</Button>
				<Button
					onClick={handleSave}
					disabled={!hasChanges || saving}
					className="flex items-center gap-2"
				>
					<Save className="h-4 w-4" />
					{saving ? "Saving..." : "Save Instructions"}
				</Button>
			</div>

			{hasChanges && (
				<Alert
					variant="default"
					className="bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800"
				>
					<Info className="h-4 w-4 text-blue-600 dark:text-blue-500" />
					<AlertDescription className="text-blue-800 dark:text-blue-300">
						You have unsaved changes. Click "Save Instructions" to apply them.
					</AlertDescription>
				</Alert>
			)}
		</div>
	);
}
