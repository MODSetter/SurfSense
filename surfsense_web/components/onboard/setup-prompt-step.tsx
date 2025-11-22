"use client";

import { ChevronDown, ChevronUp, ExternalLink, Info, Sparkles, User } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { type CommunityPrompt, useCommunityPrompts } from "@/hooks/use-community-prompts";

interface SetupPromptStepProps {
	searchSpaceId: number;
	onComplete?: () => void;
}

export function SetupPromptStep({ searchSpaceId, onComplete }: SetupPromptStepProps) {
	const { prompts, loading: loadingPrompts } = useCommunityPrompts();
	const [enableCitations, setEnableCitations] = useState(true);
	const [customInstructions, setCustomInstructions] = useState("");
	const [saving, setSaving] = useState(false);
	const [hasChanges, setHasChanges] = useState(false);
	const [selectedPromptKey, setSelectedPromptKey] = useState<string | null>(null);
	const [expandedPrompts, setExpandedPrompts] = useState<Set<string>>(new Set());
	const [selectedCategory, setSelectedCategory] = useState("all");

	// Mark that we have changes when user modifies anything
	useEffect(() => {
		setHasChanges(true);
	}, [enableCitations, customInstructions]);

	const handleSelectCommunityPrompt = (promptKey: string, promptValue: string) => {
		setCustomInstructions(promptValue);
		setSelectedPromptKey(promptKey);
		toast.success("Community prompt applied");
	};

	const toggleExpand = (promptKey: string) => {
		const newExpanded = new Set(expandedPrompts);
		if (newExpanded.has(promptKey)) {
			newExpanded.delete(promptKey);
		} else {
			newExpanded.add(promptKey);
		}
		setExpandedPrompts(newExpanded);
	};

	// Get unique categories
	const categories = Array.from(new Set(prompts.map((p) => p.category || "general")));
	const filteredPrompts =
		selectedCategory === "all"
			? prompts
			: prompts.filter((p) => (p.category || "general") === selectedCategory);

	const truncateText = (text: string, maxLength: number = 150) => {
		if (text.length <= maxLength) return text;
		return text.substring(0, maxLength) + "...";
	};

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
						Add system instructions to guide how the AI should respond. Choose from community
						prompts below or write your own.
					</p>

					{/* Community Prompts Section */}
					{!loadingPrompts && prompts.length > 0 && (
						<Card className="border-dashed">
							<CardHeader className="pb-3">
								<CardTitle className="text-sm flex items-center gap-2">
									<Sparkles className="h-4 w-4" />
									Community Prompts Library
								</CardTitle>
								<CardDescription className="text-xs">
									Browse {prompts.length} curated prompts. Click to preview or apply directly
								</CardDescription>
							</CardHeader>
							<CardContent>
								<Tabs
									value={selectedCategory}
									onValueChange={setSelectedCategory}
									className="w-full"
								>
									<TabsList className="grid w-full grid-cols-5 mb-4">
										<TabsTrigger value="all" className="text-xs">
											All ({prompts.length})
										</TabsTrigger>
										{categories.map((category) => (
											<TabsTrigger key={category} value={category} className="text-xs capitalize">
												{category} (
												{prompts.filter((p) => (p.category || "general") === category).length})
											</TabsTrigger>
										))}
									</TabsList>

									<ScrollArea className="h-[300px] pr-4">
										<div className="space-y-3">
											{filteredPrompts.map((prompt) => {
												const isExpanded = expandedPrompts.has(prompt.key);
												const isSelected = selectedPromptKey === prompt.key;
												const displayText = isExpanded
													? prompt.value
													: truncateText(prompt.value, 120);

												return (
													<div
														key={prompt.key}
														className={`p-4 rounded-lg border transition-all ${
															isSelected
																? "border-primary bg-accent/50"
																: "border-border hover:border-primary/50 hover:bg-accent/30"
														}`}
													>
														<div className="flex items-start justify-between gap-2 mb-2">
															<div className="flex items-center gap-2 flex-wrap flex-1">
																<Badge variant="outline" className="text-xs font-medium">
																	{prompt.key.replace(/_/g, " ")}
																</Badge>
																{prompt.category && (
																	<Badge variant="secondary" className="text-xs capitalize">
																		{prompt.category}
																	</Badge>
																)}
																{isSelected && (
																	<Badge variant="default" className="text-xs">
																		✓ Selected
																	</Badge>
																)}
															</div>
															{prompt.link && (
																<a
																	href={prompt.link}
																	target="_blank"
																	rel="noopener noreferrer"
																	className="text-muted-foreground hover:text-primary shrink-0"
																	title="View source"
																>
																	<ExternalLink className="h-4 w-4" />
																</a>
															)}
														</div>

														<p className="text-sm text-foreground mb-3 whitespace-pre-wrap">
															{displayText}
														</p>

														<div className="flex items-center justify-between gap-2">
															<div className="flex items-center gap-2 text-xs text-muted-foreground">
																<User className="h-3 w-3" />
																<span>{prompt.author}</span>
															</div>

															<div className="flex items-center gap-2">
																{prompt.value.length > 120 && (
																	<Button
																		type="button"
																		variant="ghost"
																		size="sm"
																		onClick={() => toggleExpand(prompt.key)}
																		className="h-7 text-xs"
																	>
																		{isExpanded ? (
																			<>
																				<ChevronUp className="h-3 w-3 mr-1" />
																				Show less
																			</>
																		) : (
																			<>
																				<ChevronDown className="h-3 w-3 mr-1" />
																				Read more
																			</>
																		)}
																	</Button>
																)}
																<Button
																	type="button"
																	variant={isSelected ? "default" : "secondary"}
																	size="sm"
																	onClick={() =>
																		handleSelectCommunityPrompt(prompt.key, prompt.value)
																	}
																	className="h-7 text-xs"
																>
																	{isSelected ? "Applied" : "Use This"}
																</Button>
															</div>
														</div>
													</div>
												);
											})}
										</div>
									</ScrollArea>
								</Tabs>
							</CardContent>
						</Card>
					)}

					<Textarea
						id="custom-instructions"
						placeholder="E.g., Always provide practical examples, be concise, focus on technical details..."
						value={customInstructions}
						onChange={(e) => {
							setCustomInstructions(e.target.value);
							setSelectedPromptKey(null);
						}}
						rows={6}
						className="resize-none"
					/>
					<div className="flex items-center justify-between">
						<p className="text-xs text-muted-foreground">{customInstructions.length} characters</p>
						{customInstructions.length > 0 && (
							<Button
								type="button"
								variant="ghost"
								size="sm"
								onClick={() => {
									setCustomInstructions("");
									setSelectedPromptKey(null);
								}}
								className="h-auto py-1 px-2 text-xs"
							>
								Clear
							</Button>
						)}
					</div>
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
