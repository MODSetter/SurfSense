"use client";

import { Info, RotateCcw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { useSearchSpace } from "@/hooks/use-search-space";

interface PromptConfigManagerProps {
	searchSpaceId: number;
}

export function PromptConfigManager({ searchSpaceId }: PromptConfigManagerProps) {
	const { searchSpace, loading, fetchSearchSpace } = useSearchSpace({
		searchSpaceId,
		autoFetch: true,
	});

	const [enableCitations, setEnableCitations] = useState(true);
	const [customInstructions, setCustomInstructions] = useState("");
	const [saving, setSaving] = useState(false);
	const [hasChanges, setHasChanges] = useState(false);

	// Initialize state from fetched search space
	useEffect(() => {
		if (searchSpace) {
			setEnableCitations(searchSpace.citations_enabled);
			setCustomInstructions(searchSpace.qna_custom_instructions || "");
			setHasChanges(false);
		}
	}, [searchSpace]);

	// Track changes
	useEffect(() => {
		if (searchSpace) {
			const currentCustom = searchSpace.qna_custom_instructions || "";

			const changed =
				searchSpace.citations_enabled !== enableCitations || currentCustom !== customInstructions;

			setHasChanges(changed);
		}
	}, [searchSpace, enableCitations, customInstructions]);

	const handleSave = async () => {
		try {
			setSaving(true);

			// Prepare payload with simplified schema
			const payload: any = {
				citations_enabled: enableCitations,
				qna_custom_instructions: customInstructions.trim() || "",
			};

			// Only send request if we have something to update
			if (Object.keys(payload).length > 0) {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/searchspaces/${searchSpaceId}`,
					{
						method: "PUT",
						headers: {
							"Content-Type": "application/json",
							Authorization: `Bearer ${localStorage.getItem("surfsense_bearer_token")}`,
						},
						body: JSON.stringify(payload),
					}
				);

				if (!response.ok) {
					const errorData = await response.json().catch(() => ({}));
					throw new Error(errorData.detail || "Failed to save prompt configuration");
				}

				toast.success("Prompt configuration saved successfully");
			}

			setHasChanges(false);

			// Refresh to get updated data
			await fetchSearchSpace();
		} catch (error: any) {
			console.error("Error saving prompt configuration:", error);
			toast.error(error.message || "Failed to save prompt configuration");
		} finally {
			setSaving(false);
		}
	};

	const handleReset = () => {
		if (searchSpace) {
			setEnableCitations(searchSpace.citations_enabled);
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
			<Alert>
				<Info className="h-4 w-4" />
				<AlertDescription>
					Configure how the AI responds to your queries. Citations add source references, and the
					system instructions personalize the response style.
				</AlertDescription>
			</Alert>

			{/* Citations Card */}
			<Card>
				<CardHeader>
					<CardTitle>Citation Configuration</CardTitle>
					<CardDescription>
						Control whether AI responses include citations to source documents
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="flex items-center justify-between space-x-4 p-4 rounded-lg border bg-card">
						<div className="flex-1 space-y-1">
							<Label htmlFor="enable-citations-settings" className="text-base font-medium">
								Enable Citations
							</Label>
							<p className="text-sm text-muted-foreground">
								When enabled, AI responses will include citations in [citation:id] format linking to
								source documents.
							</p>
						</div>
						<Switch
							id="enable-citations-settings"
							checked={enableCitations}
							onCheckedChange={setEnableCitations}
						/>
					</div>

					{!enableCitations && (
						<Alert
							variant="default"
							className="bg-yellow-50 dark:bg-yellow-950/20 border-yellow-200 dark:border-yellow-800"
						>
							<Info className="h-4 w-4 text-yellow-600 dark:text-yellow-500" />
							<AlertDescription className="text-yellow-800 dark:text-yellow-300">
								Citations are currently disabled. AI responses will not include source references.
								You can re-enable this anytime.
							</AlertDescription>
						</Alert>
					)}

					{enableCitations && (
						<Alert>
							<Info className="h-4 w-4" />
							<AlertDescription>
								Citations are enabled. When answering questions, the AI will reference source
								documents using the [citation:id] format.
							</AlertDescription>
						</Alert>
					)}
				</CardContent>
			</Card>

			{/* SearchSpace System Instructions Card */}
			<Card>
				<CardHeader>
					<CardTitle>SearchSpace System Instructions</CardTitle>
					<CardDescription>
						Add system instructions to guide the AI's response style and behavior
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="custom-instructions-settings" className="text-base font-medium">
							Your System Instructions
						</Label>
						<p className="text-sm text-muted-foreground">
							Provide specific guidelines for how you want the AI to respond. These instructions
							will be applied to all answers.
						</p>
						<Textarea
							id="custom-instructions-settings"
							placeholder="E.g., Always provide practical examples, be concise, focus on technical details, use simple language..."
							value={customInstructions}
							onChange={(e) => setCustomInstructions(e.target.value)}
							rows={8}
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
					{saving ? "Saving..." : "Save Configuration"}
				</Button>
			</div>

			{hasChanges && (
				<Alert
					variant="default"
					className="bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800"
				>
					<Info className="h-4 w-4 text-blue-600 dark:text-blue-500" />
					<AlertDescription className="text-blue-800 dark:text-blue-300">
						You have unsaved changes. Click "Save Configuration" to apply them.
					</AlertDescription>
				</Alert>
			)}
		</div>
	);
}
