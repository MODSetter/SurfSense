"use client";

import { useAtomValue } from "jotai";
import { AlertTriangle, Globe, Lock, Pencil, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
	createPromptMutationAtom,
	deletePromptMutationAtom,
	updatePromptMutationAtom,
} from "@/atoms/prompts/prompts-mutation.atoms";
import { promptsAtom } from "@/atoms/prompts/prompts-query.atoms";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ShortcutKbd } from "@/components/ui/shortcut-kbd";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import type { PromptRead } from "@/contracts/types/prompts.types";

interface PromptFormData {
	name: string;
	prompt: string;
	mode: "transform" | "explore";
	is_public: boolean;
}

const EMPTY_FORM: PromptFormData = { name: "", prompt: "", mode: "transform", is_public: false };

export function PromptsContent() {
	const { data: prompts, isLoading, isError } = useAtomValue(promptsAtom);
	const { mutateAsync: createPrompt } = useAtomValue(createPromptMutationAtom);
	const { mutateAsync: updatePrompt } = useAtomValue(updatePromptMutationAtom);
	const { mutateAsync: deletePrompt } = useAtomValue(deletePromptMutationAtom);

	const [showForm, setShowForm] = useState(false);
	const [editingId, setEditingId] = useState<number | null>(null);
	const [formData, setFormData] = useState<PromptFormData>(EMPTY_FORM);
	const [isSaving, setIsSaving] = useState(false);
	const [expandedId, setExpandedId] = useState<number | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
	const [togglingPublicIds, setTogglingPublicIds] = useState<Set<number>>(new Set());

	const handleSave = useCallback(async () => {
		if (!formData.name.trim() || !formData.prompt.trim()) {
			toast.error("Name and prompt are required");
			return;
		}

		setIsSaving(true);
		try {
			if (editingId !== null) {
				await updatePrompt({ id: editingId, ...formData });
			} else {
				await createPrompt(formData);
			}
			setShowForm(false);
			setFormData(EMPTY_FORM);
			setEditingId(null);
		} catch {
			// toast handled by mutation atoms
		} finally {
			setIsSaving(false);
		}
	}, [formData, editingId, createPrompt, updatePrompt]);

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

	const handleConfirmDelete = useCallback(async () => {
		if (deleteTarget === null) return;
		try {
			await deletePrompt(deleteTarget);
		} catch {
			// toast handled by mutation atom
		} finally {
			setDeleteTarget(null);
		}
	}, [deleteTarget, deletePrompt]);

	const handleTogglePublic = useCallback(
		async (prompt: PromptRead) => {
			if (togglingPublicIds.has(prompt.id)) return;
			setTogglingPublicIds((prev) => new Set(prev).add(prompt.id));
			try {
				await updatePrompt({ id: prompt.id, is_public: !prompt.is_public });
			} catch {
				// toast handled by mutation atom
			} finally {
				setTogglingPublicIds((prev) => {
					const next = new Set(prev);
					next.delete(prompt.id);
					return next;
				});
			}
		},
		[updatePrompt, togglingPublicIds]
	);

	const handleCancel = useCallback(() => {
		setShowForm(false);
		setFormData(EMPTY_FORM);
		setEditingId(null);
	}, []);

	const list = prompts ?? [];

	return (
		<div className="space-y-6 min-w-0 overflow-hidden">
			<div className="flex items-center justify-between">
				<p className="text-sm text-muted-foreground">
					Create prompt templates triggered with <ShortcutKbd keys={["/"]} className="ml-0" /> in
					the chat composer.
				</p>
				<Button
					size="sm"
					onClick={() => {
						setShowForm(true);
						setEditingId(null);
						setFormData(EMPTY_FORM);
					}}
					className="shrink-0 gap-1.5"
				>
					New
				</Button>
			</div>

			<Dialog
				open={showForm}
				onOpenChange={(open) => {
					setShowForm(open);
					if (!open) {
						setFormData(EMPTY_FORM);
						setEditingId(null);
					}
				}}
			>
				<DialogContent className="max-w-lg bg-popover text-popover-foreground">
					<DialogHeader>
						<DialogTitle>{editingId !== null ? "Edit prompt" : "New prompt"}</DialogTitle>
						<DialogDescription>
							Create prompt templates triggered with / in the chat composer.
						</DialogDescription>
					</DialogHeader>

					<div className="space-y-4">
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
							<Select
								value={formData.mode}
								onValueChange={(value) =>
									setFormData((p) => ({ ...p, mode: value as "transform" | "explore" }))
								}
							>
								<SelectTrigger id="prompt-mode" className="w-full">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="transform">Transform — rewrites or modifies your text</SelectItem>
									<SelectItem value="explore">Explore — answers a question about your text</SelectItem>
								</SelectContent>
							</Select>
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
					</div>

					<DialogFooter>
						<Button
							type="button"
							variant="secondary"
							size="sm"
							onClick={handleCancel}
							disabled={isSaving}
							className="text-sm h-9"
						>
							Cancel
						</Button>
						<Button
							size="sm"
							onClick={handleSave}
							disabled={isSaving}
							className="relative text-sm h-9 min-w-[96px]"
						>
							<span className={isSaving ? "opacity-0" : ""}>
								{editingId !== null ? "Update" : "Create"}
							</span>
							{isSaving && <Spinner size="sm" className="absolute" />}
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>

			{isLoading && (
				<div className="space-y-2">
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
					<AlertTitle>Failed to load prompts</AlertTitle>
					<AlertDescription>Please try refreshing the page.</AlertDescription>
				</Alert>
			)}

			{!isLoading && !isError && list.length === 0 && !showForm && (
				<div className="rounded-lg border border-dashed border-border/60 p-8 text-center">
					<Sparkles className="mx-auto size-8 text-muted-foreground/40" />
					<p className="mt-2 text-sm text-muted-foreground">No prompts yet</p>
					<p className="text-xs text-muted-foreground/60">
						Create prompts to quickly transform or explore text with /
					</p>
				</div>
			)}

			{!isLoading && !isError && list.length > 0 && (
				<div className="space-y-2">
					{list.map((prompt) => (
						<div
							key={prompt.id}
							className="group relative flex items-start gap-3 overflow-hidden rounded-lg border border-accent bg-accent/20 p-4 transition-all duration-200 hover:shadow-md"
						>
							<div className="flex-1 min-w-0">
								<div className="flex items-center gap-2">
									<span className="text-sm font-medium">{prompt.name}</span>
									<span className="rounded-md border-0 bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
										{prompt.mode}
									</span>
									{prompt.is_public && (
										<span className="flex items-center gap-1 rounded-md border-0 bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
											<Globe className="size-2.5" />
											Public
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
							<div className="flex items-center gap-1 shrink-0 opacity-0 pointer-events-none transition-opacity duration-150 group-hover:opacity-100 group-hover:pointer-events-auto">
								<Button
									type="button"
									variant="ghost"
									size="icon"
									title={prompt.is_public ? "Make private" : "Share with community"}
									onClick={() => handleTogglePublic(prompt)}
									disabled={togglingPublicIds.has(prompt.id)}
									className="h-7 w-7 rounded-lg text-muted-foreground hover:text-accent-foreground"
								>
									{togglingPublicIds.has(prompt.id) ? (
										<Spinner className="size-3.5" />
									) : prompt.is_public ? (
										<Lock className="size-3.5" />
									) : (
										<Globe className="size-3.5" />
									)}
								</Button>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7 rounded-lg text-muted-foreground hover:text-accent-foreground"
									onClick={() => handleEdit(prompt)}
								>
									<Pencil className="size-3.5" />
								</Button>
								<Button
									variant="ghost"
									size="icon"
									className="h-7 w-7 rounded-lg text-muted-foreground hover:text-destructive"
									onClick={() => setDeleteTarget(prompt.id)}
								>
									<Trash2 className="size-3.5" />
								</Button>
							</div>
						</div>
					))}
				</div>
			)}

			<AlertDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle>Delete prompt</AlertDialogTitle>
						<AlertDialogDescription>
							This action cannot be undone. The prompt will be permanently removed.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel>Cancel</AlertDialogCancel>
						<AlertDialogAction onClick={handleConfirmDelete}>Delete</AlertDialogAction>
					</AlertDialogFooter>
				</AlertDialogContent>
			</AlertDialog>
		</div>
	);
}
