"use client";

import { Globe, PenLine, Plus, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type { PromptRead } from "@/contracts/types/prompts.types";
import { promptsApiService } from "@/lib/apis/prompts-api.service";

interface PromptFormData {
	name: string;
	prompt: string;
	mode: "transform" | "explore";
	is_public: boolean;
}

const EMPTY_FORM: PromptFormData = { name: "", prompt: "", mode: "transform", is_public: false };

export function PromptsContent() {
	const [prompts, setPrompts] = useState<PromptRead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [showForm, setShowForm] = useState(false);
	const [editingId, setEditingId] = useState<number | null>(null);
	const [formData, setFormData] = useState<PromptFormData>(EMPTY_FORM);
	const [isSaving, setIsSaving] = useState(false);

	useEffect(() => {
		promptsApiService
			.list()
			.then(setPrompts)
			.catch(() => toast.error("Failed to load prompts"))
			.finally(() => setIsLoading(false));
	}, []);

	const handleSave = useCallback(async () => {
		if (!formData.name.trim() || !formData.prompt.trim()) {
			toast.error("Name and prompt are required");
			return;
		}

		setIsSaving(true);
		try {
			if (editingId) {
				const updated = await promptsApiService.update(editingId, formData);
				setPrompts((prev) => prev.map((p) => (p.id === editingId ? updated : p)));
				toast.success("Prompt updated");
			} else {
				const created = await promptsApiService.create(formData);
				setPrompts((prev) => [created, ...prev]);
				toast.success("Prompt created");
			}
			setShowForm(false);
			setFormData(EMPTY_FORM);
			setEditingId(null);
		} catch {
			toast.error("Failed to save prompt");
		} finally {
			setIsSaving(false);
		}
	}, [formData, editingId]);

	const handleEdit = useCallback((prompt: PromptRead) => {
		setFormData({
			name: prompt.name,
			prompt: prompt.prompt,
			mode: prompt.mode as "transform" | "explore",
			is_public: prompt.is_public,
		});
		setEditingId(prompt.id);
		setShowForm(true);
	}, []);

	const handleDelete = useCallback(async (id: number) => {
		try {
			await promptsApiService.delete(id);
			setPrompts((prev) => prev.filter((p) => p.id !== id));
			toast.success("Prompt deleted");
		} catch {
			toast.error("Failed to delete prompt");
		}
	}, []);

	const handleCancel = useCallback(() => {
		setShowForm(false);
		setFormData(EMPTY_FORM);
		setEditingId(null);
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
			<div className="flex items-center justify-between">
				<p className="text-sm text-muted-foreground">
					Create prompt templates triggered with{" "}
					<kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs font-mono">/</kbd> in the
					chat composer.
				</p>
				{!showForm && (
					<Button
						size="sm"
						onClick={() => {
							setShowForm(true);
							setEditingId(null);
							setFormData(EMPTY_FORM);
						}}
						className="shrink-0 gap-1.5"
					>
						<Plus className="size-3.5" />
						New
					</Button>
				)}
			</div>

			{showForm && (
				<div className="rounded-lg border border-border/60 bg-card p-6 space-y-4">
					<h3 className="text-sm font-semibold tracking-tight">
						{editingId ? "Edit prompt" : "New prompt"}
					</h3>

					<div className="space-y-2">
						<Label htmlFor="prompt-name">Name</Label>
						<Input
							id="prompt-name"
							value={formData.name}
							onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
							placeholder="e.g. Fix grammar"
						/>
					</div>

					<div className="space-y-2">
						<Label htmlFor="prompt-template">Prompt template</Label>
						<textarea
							id="prompt-template"
							value={formData.prompt}
							onChange={(e) => setFormData((p) => ({ ...p, prompt: e.target.value }))}
							placeholder="e.g. Fix the grammar in the following text:\n\n{selection}"
							rows={4}
							className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none resize-none focus:ring-1 focus:ring-ring"
						/>
						<p className="text-xs text-muted-foreground">
							Use{" "}
							<code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">
								{"{selection}"}
							</code>{" "}
							to insert the input text. If omitted, the text is appended automatically.
						</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="prompt-mode">Mode</Label>
						<select
							id="prompt-mode"
							value={formData.mode}
							onChange={(e) =>
								setFormData((p) => ({ ...p, mode: e.target.value as "transform" | "explore" }))
							}
							className="w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-ring"
						>
							<option value="transform">Transform — rewrites or modifies your text</option>
							<option value="explore">Explore — answers a question about your text</option>
						</select>
					</div>

				<div className="flex items-center gap-2">
					<Switch
						id="prompt-public"
						checked={formData.is_public}
						onCheckedChange={(checked) => setFormData((p) => ({ ...p, is_public: checked }))}
					/>
					<Label htmlFor="prompt-public" className="text-sm font-normal">
						Share with community
					</Label>
				</div>

				<div className="flex items-center justify-end gap-2 pt-2">
					<Button variant="ghost" size="sm" onClick={handleCancel}>
						Cancel
					</Button>
					<Button size="sm" onClick={handleSave} disabled={isSaving}>
						{isSaving ? <Spinner className="size-3.5" /> : editingId ? "Update" : "Create"}
					</Button>
				</div>
				</div>
			)}

			{prompts.length === 0 && !showForm && (
				<div className="rounded-lg border border-dashed border-border/60 p-8 text-center">
					<Sparkles className="mx-auto size-8 text-muted-foreground/40" />
					<p className="mt-2 text-sm text-muted-foreground">No custom prompts yet</p>
					<p className="text-xs text-muted-foreground/60">
						Create prompts to quickly transform or explore text with /
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
									{prompt.is_public && (
										<span className="flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-2 py-0.5 text-[10px] text-primary">
											<Globe className="size-2.5" />
											Public
										</span>
									)}
								</div>
								<p className="mt-1 text-xs text-muted-foreground line-clamp-2">{prompt.prompt}</p>
							</div>
							<div className="hidden group-hover:flex items-center gap-1 shrink-0">
								<Button
									variant="ghost"
									size="icon"
									className="size-7"
									onClick={() => handleEdit(prompt)}
								>
									<PenLine className="size-3.5" />
								</Button>
								<Button
									variant="ghost"
									size="icon"
									className="size-7 text-destructive hover:text-destructive"
									onClick={() => handleDelete(prompt.id)}
								>
									<Trash2 className="size-3.5" />
								</Button>
							</div>
						</div>
					))}
				</div>
			)}
		</div>
	);
}
