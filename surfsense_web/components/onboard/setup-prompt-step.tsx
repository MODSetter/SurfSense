"use client";

import { Info } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

interface SetupPromptStepProps {
	searchSpaceId: number;
	onComplete?: () => void;
}

export function SetupPromptStep({ searchSpaceId, onComplete }: SetupPromptStepProps) {
	const [enableCitations, setEnableCitations] = useState(true);
	const [customInstructions, setCustomInstructions] = useState("");
	const [saving, setSaving] = useState(false);
	const [hasChanges, setHasChanges] = useState(false);

	// Mark that we have changes when user modifies anything
	useEffect(() => {
		setHasChanges(true);
	}, [enableCitations, customInstructions]);

	const handleSave = async () => {
		try {
			setSaving(true);

			// Prepare the update payload with simplified schema
			const payload: any = {
				citations_enabled: enableCitations,
				qna_custom_instructions: customInstructions.trim() || "",
			};

			// Only send update if there's something to update
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
					throw new Error(
						errorData.detail || `Failed to save prompt configuration (${response.status})`
					);
				}

				toast.success("Prompt configuration saved successfully");
			}

			setHasChanges(false);
			onComplete?.();
		} catch (error: any) {
			console.error("Error saving prompt configuration:", error);
			toast.error(error.message || "Failed to save prompt configuration");
		} finally {
			setSaving(false);
		}
	};

	const handleSkip = () => {
		// Skip without saving - use defaults
		onComplete?.();
	};

	return (
		<div className="space-y-6">
			<Alert>
				<Info className="h-4 w-4" />
				<AlertDescription>
					These settings are optional. You can skip this step and configure them later in settings.
				</AlertDescription>
			</Alert>

			{/* Citation Toggle */}
			<div className="space-y-4">
				<div className="flex items-center justify-between space-x-4 p-4 rounded-lg border bg-card">
					<div className="flex-1 space-y-1">
						<Label htmlFor="enable-citations" className="text-base font-medium">
							Enable Citations
						</Label>
						<p className="text-sm text-muted-foreground">
							When enabled, AI responses will include citations to source documents using
							[citation:id] format.
						</p>
					</div>
					<Switch
						id="enable-citations"
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
							Disabling citations means AI responses won't include source references. You can
							re-enable this anytime in settings.
						</AlertDescription>
					</Alert>
				)}
			</div>

			{/* SearchSpace System Instructions */}
			<div className="space-y-4">
				<div className="space-y-2">
					<Label htmlFor="custom-instructions" className="text-base font-medium">
						SearchSpace System Instructions (Optional)
					</Label>
					<p className="text-sm text-muted-foreground">
						Add system instructions to guide how the AI should respond. For example: "Always provide
						code examples" or "Keep responses concise and technical".
					</p>
					<Textarea
						id="custom-instructions"
						placeholder="E.g., Always provide practical examples, be concise, focus on technical details..."
						value={customInstructions}
						onChange={(e) => setCustomInstructions(e.target.value)}
						rows={6}
						className="resize-none"
					/>
					<p className="text-xs text-muted-foreground">{customInstructions.length} characters</p>
				</div>
			</div>

			{/* Action Buttons */}
			<div className="flex items-center justify-between pt-4 border-t">
				<Button variant="ghost" onClick={handleSkip} disabled={saving}>
					Skip for now
				</Button>
				<Button onClick={handleSave} disabled={saving || !hasChanges}>
					{saving ? "Saving..." : "Save Configuration"}
				</Button>
			</div>
		</div>
	);
}
